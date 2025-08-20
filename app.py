import requests
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import pandas as pd
from bs4 import BeautifulSoup
import streamlit as st
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

# -----------------------------
# User-Agent rotation
# -----------------------------
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:92.0)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
]

def get_headers():
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Accept-Encoding": "gzip",
        "Pragma": "no-cache"
    }

# -----------------------------
# Safe request wrapper
# -----------------------------
def safe_request(url, timeout=15):
    try:
        response = requests.get(url, headers=get_headers(), timeout=timeout)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as e:
        st.warning(f"HTTP error for {url}: {e}")
    except requests.exceptions.RequestException as e:
        st.warning(f"Request failed for {url}: {e}")
    return None

# -----------------------------
# Extract metadata from a page
# -----------------------------
def extract_page_metadata(url):
    try:
        response = safe_request(url)
        if not response:
            return url, "", "", ""

        soup = BeautifulSoup(response.content, 'html.parser')

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        description_tag = soup.find("meta", attrs={"name": "description"})
        description = description_tag["content"].strip() if description_tag and "content" in description_tag.attrs else ""
        h1_tag = soup.find("h1")
        h1 = h1_tag.get_text().strip() if h1_tag else ""

        return url, title, description, h1
    except Exception as e:
        st.warning(f"Metadata extraction failed for {url}: {e}")
        return url, "", "", ""

# -----------------------------
# Parse sitemap (index or file)
# -----------------------------
def analyze_sitemap_generic(sitemap_url):
    response = safe_request(sitemap_url)
    if not response:
        return []

    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        st.error(f"Could not parse sitemap XML: {sitemap_url}")
        return []

    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

    if root.tag.endswith('sitemapindex'):
        return [loc.text for loc in root.findall('.//sm:loc', ns)]
    elif root.tag.endswith('urlset'):
        return [loc.text for loc in root.findall('.//sm:loc', ns)]
    return []

# -----------------------------
# Analyze a single sitemap file
# -----------------------------
def analyze_sitemap(sitemap_url):
    urls = analyze_sitemap_generic(sitemap_url)
    url_count = len(urls)
    top_level_directories = {}

    for url in urls:
        parsed_url = urlparse(url)
        path_parts = parsed_url.path.split('/')
        if parsed_url.path in ("/", ""):
            top_level_dir = "Homepage"
        elif len(path_parts) == 2:
            top_level_dir = "Others"
        else:
            top_level_dir = path_parts[1]

        top_level_directories[top_level_dir] = top_level_directories.get(top_level_dir, 0) + 1

    return url_count, top_level_directories, urls

# -----------------------------
# Fetch metadata in parallel
# -----------------------------
def fetch_all_metadata(urls, max_workers=10):
    results = []
    progress = st.progress(0)
    futures = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for url in urls:
            futures.append(executor.submit(extract_page_metadata, url))

        for i, future in enumerate(as_completed(futures)):
            results.append(future.result())
            progress.progress((i + 1) / len(urls))

    return results

# -----------------------------
# Streamlit UI
# -----------------------------
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
            all_sitemaps.extend(analyze_sitemap_generic(sitemap_index_url))

        if exclude_path:
            all_sitemaps = [s for s in all_sitemaps if exclude_path.lower() not in s.lower()]

        st.write(f"Analyzing {len(all_sitemaps)} sitemap files. Please wait...")

        sitemap_info = {}
        for sitemap in all_sitemaps:
            url_count, top_level_dirs, urls = analyze_sitemap(sitemap)
            sitemap_info[sitemap] = {
                'url_count': url_count,
                'top_level_directories': top_level_dirs,
                'urls': urls
            }

        # Collect all URLs across all sitemaps
        all_urls = [url for info in sitemap_info.values() for url in info['urls']]
        st.write(f"Extracting metadata from {len(all_urls)} URLs...")

        metadata = fetch_all_metadata(all_urls, max_workers=10)

        url_data = []
        for url, title, desc, h1 in metadata:
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.split('/')
            if parsed_url.path in ("/", ""):
                top_level_dir = "Homepage"
            elif len(path_parts) == 2:
                top_level_dir = "Others"
            else:
                top_level_dir = path_parts[1]

            url_data.append({
                'Sitemap': "Multiple",
                'URL': url,
                'Top-Level Directory': top_level_dir,
                'Page Title': title,
                'Meta Description': desc,
                'H1': h1
            })

        url_df = pd.DataFrame(url_data)
        st.subheader("All URLs with Metadata")
        st.dataframe(url_df.head(200))
        st.download_button("Download CSV", url_df.to_csv(index=False).encode('utf-8'),
                           "sitemap_urls.csv", "text/csv")

elif analysis_type == "Sitemap File(s)":
    sitemap_urls = st.text_area("Enter the Sitemap File(s), one per line:")
    if st.button("Run Analysis"):
        sitemaps = [url.strip() for url in sitemap_urls.split('\n') if url.strip()]
        sitemap_info = {}
        for sitemap in sitemaps:
            url_count, top_level_dirs, urls = analyze_sitemap(sitemap)
            sitemap_info[sitemap] = {
                'url_count': url_count,
                'top_level_directories': top_level_dirs,
                'urls': urls
            }

        # Collect all URLs
        all_urls = [url for info in sitemap_info.values() for url in info['urls']]
        st.write(f"Extracting metadata from {len(all_urls)} URLs...")

        metadata = fetch_all_metadata(all_urls, max_workers=10)

        url_data = []
        for url, title, desc, h1 in metadata:
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.split('/')
            if parsed_url.path in ("/", ""):
                top_level_dir = "Homepage"
            elif len(path_parts) == 2:
                top_level_dir = "Others"
            else:
                top_level_dir = path_parts[1]

            url_data.append({
                'Sitemap': "Multiple",
                'URL': url,
                'Top-Level Directory': top_level_dir,
                'Page Title': title,
                'Meta Description': desc,
                'H1': h1
            })

        url_df = pd.DataFrame(url_data)
        st.subheader("All URLs with Metadata")
        st.dataframe(url_df.head(200))
        st.download_button("Download CSV", url_df.to_csv(index=False).encode('utf-8'),
                           "sitemap_urls.csv", "text/csv")

st.divider()
