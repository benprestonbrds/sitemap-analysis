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
    except Exception:
        return "", "", ""

def analyze_sitemap_index(sitemap_index_url):
    response = requests.get(sitemap_index_url, headers=headers)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    namespaces = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    if root.tag.endswith('sitemapindex'):
        return [loc.text for loc in root.findall('.//sm:loc', namespaces)]
    elif root.tag.endswith('urlset'):
        return [loc.text for loc in root.findall('.//sm:loc', namespaces)]
    else:
        return []

def analyze_sitemap(sitemap_url):
    response = requests.get(sitemap_url, headers=headers)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    url_count = 0
    top_level_directories = {}
    urls = []

    for url_elem in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc_elem is not None:
            url = loc_elem.text
            url_count += 1
            urls.append(url)
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.split('/')
            if parsed_url.path == "/" or parsed_url.path == "":
                top_level_dir = "Homepage"
            elif len(path_parts) == 2:
                top_level_dir = "Others"
            else:
                top_level_dir = path_parts[1]

            if top_level_dir in top_level_directories:
                top_level_directories[top_level_dir] += 1
            else:
                top_level_directories[top_level_dir] = 1

    return url_count, top_level_directories, urls

# Streamlit UI
st.header("Overdose Sitemap Analyzer", divider='rainbow')
analysis_type = st.radio("Choose analysis type:", ("Sitemap Index", "Sitemap File(s)"))

if analysis_type == "Sitemap Index":
    sitemap_index_urls = st.text_area("Enter the Sitemap Index URL(s), one per line:")
    with st.expander("Advanced Settings"):
        exclude_path = st.text_input("Exclude sitemaps containing this path (optional):")

    if st.button("Run Analysis"):
        sitemap_indexes = [url.strip() for url in sitemap_index_urls.split('\n') if url.strip()]
        all_sitemaps = []
        for sitemap_index_url in sitemap_indexes:
            all_sitemaps.extend(analyze_sitemap_index(sitemap_index_url))

        if exclude_path:
            all_sitemaps = [s for s in all_sitemaps if exclude_path.lower() not in s.lower()]

        st.write(f"Analyzing {len(all_sitemaps)} sitemap files. Please wait...")

        sitemap_info = {}
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, sitemap in enumerate(all_sitemaps):
            status_text.markdown(f"Analyzing: {sitemap}")
            url_count, top_level_dirs, urls = analyze_sitemap(sitemap)
            sitemap_info[sitemap] = {
                'url_count': url_count,
                'top_level_directories': top_level_dirs,
                'urls': urls
            }
            progress_bar.progress((idx + 1) / len(all_sitemaps))

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

        url_df = pd.DataFrame(url_data)
        st.subheader("All URLs with Metadata")
        st.dataframe(url_df.head(200))
        st.download_button("Download CSV", url_df.to_csv().encode('utf-8'), "sitemap_urls.csv", "text/csv")

elif analysis_type == "Sitemap File(s)":
    sitemap_urls = st.text_area("Enter the Sitemap File(s), one per line:")
    if st.button("Run Analysis"):
        sitemaps = [url.strip() for url in sitemap_urls.split('\n') if url.strip()]
        sitemap_info = {}
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, sitemap in enumerate(sitemaps):
            status_text.markdown(f"Analyzing: {sitemap}")
            url_count, top_level_dirs, urls = analyze_sitemap(sitemap)
            sitemap_info[sitemap] = {
                'url_count': url_count,
                'top_level_directories': top_level_dirs,
                'urls': urls
            }
            progress_bar.progress((idx + 1) / len(sitemaps))

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

        url_df = pd.DataFrame(url_data)
        st.subheader("All URLs with Metadata")
        st.dataframe(url_df.head(200))
        st.download_button("Download CSV", url_df.to_csv().encode('utf-8'), "sitemap_urls.csv", "text/csv")

st.divider()
