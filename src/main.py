import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime


def scrape_jobs(url):
    """
    Función base para scraping de empleos.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error al obtener la página: {e}")
        return None


def parse_job_listing(html):
    """
    Parser básico para listados de empleos.
    """
    soup = BeautifulSoup(html, 'lxml')
    jobs = []
    
    # Ejemplo básico - personalizar según la estructura del sitio
    job_elements = soup.find_all('div', class_='job-listing')
    
    for job in job_elements:
        title = job.find('h2')
        company = job.find('span', class_='company')
        location = job.find('span', class_='location')
        
        jobs.append({
            'title': title.text.strip() if title else 'N/A',
            'company': company.text.strip() if company else 'N/A',
            'location': location.text.strip() if location else 'N/A',
            'scraped_at': datetime.now().isoformat()
        })
    
    return jobs


def save_to_csv(jobs, filename='jobs.csv'):
    """
    Guarda los empleos en un archivo CSV.
    """
    df = pd.DataFrame(jobs)
    df.to_csv(f'data/{filename}', index=False, encoding='utf-8')
    print(f"Guardados {len(jobs)} empleos en data/{filename}")


if __name__ == '__main__':
    # Ejemplo de uso
    url = "https://example.com/jobs"
    html = scrape_jobs(url)
    
    if html:
        jobs = parse_job_listing(html)
        save_to_csv(jobs)