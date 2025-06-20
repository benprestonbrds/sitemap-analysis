import requests
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Accept-Encoding": "gzip",
    "Pragma": "no-cache"
}

def analyze_sitemap_index(sitemap_index_url):
    """Analyze the Sitemap Index file and extract the URLs of the Sitemaps."""
    
    response = requests.get(sitemap_index_url, headers=headers)
    response.raise_for_status()  # Check for errors

    root = ET.fromstring(response.content)

    namespaces = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    locs = []
    
    # Check if it's a sitemap index
    if root.tag.endswith('sitemapindex'):
        locs = [loc.text for loc in root.findall('.//sm:loc', namespaces)]
    # Check if it's a regular sitemap
    elif root.tag.endswith('urlset'):
        locs = [loc.text for loc in root.findall('.//sm:loc', namespaces)]
    else:
        print("Unknown sitemap format")
    
    return locs

def analyze_sitemap(sitemap_url):
    """Analyze the Sitemap file, count the number of URLs, and extract the top-level directory and its URL count."""

    response = requests.get(sitemap_url, headers=headers)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    url_count = 0
    top_level_directories = {}
    urls = []

    for url_elem in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc_elem is not None:
            url_count += 1
            urls.append(loc_elem.text)
            parsed_url = urlparse(loc_elem.text)
            path_parts = parsed_url.path.split('/')
            if parsed_url.path == "/" or parsed_url.path == "":
                top_level_dir = "Homepage"
            elif len(path_parts) == 2:
                top_level_dir = "Others"
            else:
                top_level_dir = path_parts[1]

            title, description, h1 = extract_page_metadata(url)  # Extract top-level directory
            if top_level_dir in top_level_directories:
                top_level_directories[top_level_dir] += 1
            else:
                top_level_directories[top_level_dir] = 1

    return url_count, top_level_directories, urls



def extract_page_metadata(url):
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        
        description_tag = soup.find("meta", attrs={"name": "description"})
        description = description_tag["content"].strip() if description_tag and "content" in description_tag.attrs else ""
        
        h1_tag = soup.find("h1")
        h1 = h1_tag.get_text().strip() if h1_tag else ""
        
        return title, description, h1
    except Exception as e:
        return "", "", ""


# Streamlit app
st.header("Overdose Sitemap Analyzer", divider='rainbow')

analysis_type = st.radio("Choose analysis type:", ("Sitemap Index", "Sitemap File(s)"))

if analysis_type == "Sitemap Index":
    sitemap_index_urls = st.text_area("Enter the Sitemap Index URL(s), one per line:")
    with st.expander("Advanced Settings"):
        exclude_path = st.text_input("Exclude sitemaps containing this path (optional):")
    
    if st.button("Run Analysis"):
        if sitemap_index_urls:
            sitemap_indexes = [url.strip() for url in sitemap_index_urls.split('\n') if url.strip()]
            if len(sitemap_indexes) > 0:
                try:
                    all_sitemaps = []
                    for sitemap_index_url in sitemap_indexes:
                        sitemaps = analyze_sitemap_index(sitemap_index_url)
                        all_sitemaps.extend(sitemaps)
                    
                    total_sitemaps = len(all_sitemaps)
                    
                    # Filter sitemaps based on the exclude_path
                    if exclude_path:
                        all_sitemaps = [s for s in all_sitemaps if exclude_path.lower() not in s.lower()]
                    
                    excluded_sitemaps = total_sitemaps - len(all_sitemaps)
                    
                    st.write(f"Discovered {total_sitemaps} sitemap files across {len(sitemap_indexes)} sitemap index(es).")
                    if excluded_sitemaps > 0:
                        st.write(f"Excluded {excluded_sitemaps} sitemaps from the analysis.")
                    st.write(f"Analyzing {len(all_sitemaps)} sitemap files. Please wait...")

                    sitemap_info = {}
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    for idx, sitemap in enumerate(all_sitemaps):
                        status_text.markdown(f"<span style='color:grey'>({idx + 1}/{len(all_sitemaps)}) Analyzing: {sitemap}</span>", unsafe_allow_html=True)
                        url_count, top_level_dirs, urls = analyze_sitemap(sitemap)
                        sitemap_info[sitemap] = {
                            'url_count': url_count,
                            'top_level_directories': top_level_dirs,
                            'urls': urls
                        }
                        progress_bar.progress((idx + 1) / len(all_sitemaps))
                    status_text.markdown("<span style='color:grey'>Analysis Complete</span>", unsafe_allow_html=True)


                    # Construct data for DataFrame
                    data = []
                    for sitemap, info in sitemap_info.items():
                        row = {'Sitemap': sitemap, 'URL Count': int(info['url_count'])}  # Ensure URL Count has no decimal points
                        row.update(info['top_level_directories'])
                        data.append(row)

                    # Create DataFrame
                    df = pd.DataFrame(data)
                    df.set_index('Sitemap', inplace=True)

                    # Convert all NaN values to 0
                    df.fillna(0, inplace=True)
                    # Add a row at the top that sums the number of all other cells in the same column
                    sum_row = df.sum(numeric_only=True)
                    sum_row.name = 'TOTAL'
                    df = pd.concat([sum_row.to_frame().T, df])
                    df.sort_values(by='URL Count', ascending=False, inplace=True)
                    # Display header
                    st.subheader("Analysis Overview")


                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Number of Sitemap Indexes", f"{len(sitemap_indexes)}")
                    col2.metric("Number of Sitemaps", f"{len(all_sitemaps)}")
                    col3.metric("Number of URLs", int(sum_row['URL Count']))
                    col4.metric("Number of Top Level Directories", f"{len(df.columns) - 2}")

                    with st.spinner('Loading...'):
                        # Display DataFrame with increased width and highlighted non-zero cells
                        st.dataframe(df)
                    st.balloons()

                    # Construct data for URL DataFrame
                    url_data = []
                    for sitemap, info in sitemap_info.items():
                        for url in info['urls']:
                            parsed_url = urlparse(url)
                            path_parts = parsed_url.path.split('/')
                            if parsed_url.path == "/" or parsed_url.path == "":
                                top_level_dir = "Homepage"
                            elif len(path_parts) == 2:
                                top_level_dir = "Others"
                            else:
                                top_level_dir = path_parts[1]

            title, description, h1 = extract_page_metadata(url)
                            url_data.append({
        'Sitemap': sitemap,
        'URL': url,
        'Top-Level Directory': top_level_dir,
        'Page Title': title,
        'Meta Description': description,
        'H1': h1
    })

                    # Create URL DataFrame
                    url_df = pd.DataFrame(url_data)

                    # Display header
                    st.subheader("All URLs")

                    # Display only the first 200 rows of the URL DataFrame
                    with st.spinner('Loading...'):
                        st.dataframe(url_df.head(200))
                    st.write(f"Note: This is just a preview. The full dataset contains {len(url_df)} URLs. Please download to see them all.")

                    # Provide a downloadable button for full URL DataFrame
                    url_csv = url_df.to_csv().encode('utf-8')
                    st.download_button(
                        label="Download URL data as CSV",
                        data=url_csv,
                        file_name='sitemap_urls.csv',
                        mime='text/csv',
                        on_click=lambda: st.session_state.update({"downloaded": True})
                    )
                except requests.exceptions.RequestException as e:
                    st.error(f"An error occurred: {e}")
                    st.write("The website might have some bot detection that prevents the script from working.")
            else:
                st.error("Please enter at least one valid Sitemap Index URL.")
        else:
            st.error("Please enter at least one valid Sitemap Index URL.")
            st.write("The website might have some bot detection that prevents the script from working.")
            
elif analysis_type == "Sitemap File(s)":
    sitemap_urls = st.text_area("Enter the Sitemap File(s), one per line:")
    if st.button("Run Analysis"):
        if sitemap_urls:
            sitemaps = [url.strip() for url in sitemap_urls.split('\n') if url.strip()]
            if len(sitemaps) > 0:
                try:
                    st.write(f"Discovered {len(sitemaps)} sitemap file(s).")
                    sitemap_info = {}
                    progress_bar = st.progress(0)
                    total_sitemaps = len(sitemaps)
                    status_text = st.empty()
                    
                    for idx, sitemap in enumerate(sitemaps):
                        status_text.markdown(f"<span style='color:grey'>({idx + 1}/{total_sitemaps}) Analyzing: {sitemap}</span>", unsafe_allow_html=True)
                        url_count, top_level_dirs, urls = analyze_sitemap(sitemap)
                        sitemap_info[sitemap] = {
                            'url_count': url_count,
                            'top_level_directories': top_level_dirs,
                            'urls': urls
                        }
                        progress_bar.progress((idx + 1) / total_sitemaps)
                    status_text.markdown("<span style='color:grey'>Analysis Complete</span>", unsafe_allow_html=True)

                    # Construct data for DataFrame
                    data = []
                    for sitemap, info in sitemap_info.items():
                        row = {'Sitemap': sitemap, 'URL Count': int(info['url_count'])}
                        row.update(info['top_level_directories'])
                        data.append(row)

                    # Create DataFrame
                    df = pd.DataFrame(data)
                    df.set_index('Sitemap', inplace=True)

                    # Convert all NaN values to 0
                    df.fillna(0, inplace=True)
                    # Add a row at the top that sums the number of all other cells in the same column
                    sum_row = df.sum(numeric_only=True)
                    sum_row.name = 'TOTAL'
                    df = pd.concat([sum_row.to_frame().T, df])
                    df.sort_values(by='URL Count', ascending=False, inplace=True)
                    
                    # Display header
                    st.subheader("Analysis Overview")

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Number of Sitemaps", f"{total_sitemaps}")
                    col2.metric("Number of URLs", int(sum_row['URL Count']))
                    col3.metric("Number of Top Level Directories", f"{len(df.columns) - 2}")
                    
                    with st.spinner('Loading...'):
                        # Display DataFrame with increased width and highlighted non-zero cells
                        st.dataframe(df)
                    st.balloons()

                    # Construct data for URL DataFrame
                    url_data = []
                    for sitemap, info in sitemap_info.items():
                        for url in info['urls']:
                            parsed_url = urlparse(url)
                            path_parts = parsed_url.path.split('/')
                            if parsed_url.path == "/" or parsed_url.path == "":
                                top_level_dir = "Homepage"
                            elif len(path_parts) == 2:
                                top_level_dir = "Others"
                            else:
                                top_level_dir = path_parts[1]

            title, description, h1 = extract_page_metadata(url)
                            url_data.append({
        'Sitemap': sitemap,
        'URL': url,
        'Top-Level Directory': top_level_dir,
        'Page Title': title,
        'Meta Description': description,
        'H1': h1
    })

                    # Create URL DataFrame
                    url_df = pd.DataFrame(url_data)

                    # Display header
                    st.subheader("All URLs")

                    # Display only the first 200 rows of the URL DataFrame
                    with st.spinner('Loading...'):
                        st.dataframe(url_df.head(200))
                    st.write(f"Note: This is just a preview. The full dataset contains {len(url_df)} URLs. Please download to see them all.")

                    # Provide a downloadable button for full URL DataFrame
                    url_csv = url_df.to_csv().encode('utf-8')
                    st.download_button(
                        label="Download URL data as CSV",
                        data=url_csv,
                        file_name='sitemap_urls.csv',
                        mime='text/csv',
                        on_click=lambda: st.session_state.update({"downloaded": True})
                    )
                except requests.exceptions.RequestException as e:
                    st.error(f"An error occurred: {e}")
                    st.write("The website might have some bot detection that prevents the script from working.")
            else:
                st.error("Please enter at least one valid Sitemap URL.")
        else:
            st.error("Please enter at least one valid Sitemap URL.")
            st.write("The website might have some bot detection that prevents the script from working.")

st.divider()
