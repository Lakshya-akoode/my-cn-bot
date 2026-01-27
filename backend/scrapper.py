import requests
from bs4 import BeautifulSoup

import re

URLS = [
    "https://mycnmedical.com/",
    "https://mycnmedical.com/services/",
    "https://mycnmedical.com/services/medical-weight-loss/",
    "https://mycnmedical.com/services/fillers-injectables/neuromodulators-toxins/tmj-tox/",
    "https://mycnmedical.com/services/fillers-injectables/neuromodulators-toxins/nefertiti-neck-lift/",
    "https://mycnmedical.com/services/fillers-injectables/neuromodulators-toxins/barbie-tox-trap-tox/",
    "https://mycnmedical.com/services/fillers-injectables/dermal-fillers/",
    "https://mycnmedical.com/services/facials-and-skin-treatments/dermaplaning/",
    "https://mycnmedical.com/services/facials-and-skin-treatments/hydrodermabrasion/",
    "https://mycnmedical.com/services/facials-and-skin-treatments/signature-facial/",
    "https://mycnmedical.com/services/laser/co2-laser-skin-resurfacing/",
    "https://mycnmedical.com/services/fillers-injectables/neuromodulators-toxins/",
    "https://mycnmedical.com/services/fillers-injectables/neuromodulators-toxins/lip-flip/",
    "https://mycnmedical.com/services/facials-and-skin-treatments/microdermabrasion/",
    "https://mycnmedical.com/services/regenerative-medicine/prp-injections/",
    "https://mycnmedical.com/services/regenerative-medicine/sculptra-aesthetic-facial-injectable/",
    "https://mycnmedical.com/services/regenerative-medicine/exosomes/",
    "https://mycnmedical.com/services/regenerative-medicine/iv-therapy/",
    "https://mycnmedical.com/services/targeted-skin-concerns/acne-scars/",
    "https://mycnmedical.com/services/targeted-skin-concerns/age-spots/",
    "https://mycnmedical.com/services/targeted-skin-concerns/anti-aging-treatments/",
    "https://mycnmedical.com/services/targeted-skin-concerns/ipl-for-spider-veins/",
    "https://mycnmedical.com/services/targeted-skin-concerns/sun-damage/",
    "https://mycnmedical.com/services/fillers-injectables/neuromodulators-toxins/botox-cosmetic/",
    "https://mycnmedical.com/services/fillers-injectables/neuromodulators-toxins/dysport-injectable/",
    "https://mycnmedical.com/services/fillers-injectables/neuromodulators-toxins/jeuveau/",
    "https://mycnmedical.com/services/wellness-and-weight-loss/cellulite/",
    "https://mycnmedical.com/services/wellness-and-weight-loss/vitamin-injections/",
    "https://mycnmedical.com/services/fillers-injectables/filler-removal/",
    "https://mycnmedical.com/services/fillers-injectables/juvederm/",
    "https://mycnmedical.com/services/fillers-injectables/rh-filler/",
    "https://mycnmedical.com/services/laser/intense-pulse-light-ipl/",
    "https://mycnmedical.com/services/laser/laser-pigment-removal/",
    "https://mycnmedical.com/services/laser/radiofrequency-microneedling/",
    "https://mycnmedical.com/services/laser/skin-tightening/",
    "https://mycnmedical.com/services/facials-and-skin-treatments/microneedling/",
    "https://mycnmedical.com/services/facials-and-skin-treatments/microneedling-prp/",
    "https://mycnmedical.com/services/fillers-injectables/dermal-fillers/restylane-injectable-gel/",
    "https://mycnmedical.com/services/fillers-injectables/kybella/",
    "https://mycnmedical.com/services/medical-weight-loss/semaglutide-injections/",
    "https://mycnmedical.com/services/regenerative-medicine/",
    "https://mycnmedical.com/services/facials-and-skin-treatments/",
    "https://mycnmedical.com/services/laser/",
    "https://mycnmedical.com/services/prp-hair-restoration/",
    "https://mycnmedical.com/services/fillers-injectables/",
    "https://mycnmedical.com/services/targeted-skin-concerns/",
    "https://mycnmedical.com/services/facials-and-skin-treatments/chemical-peels/"
]

def scrape():
    texts = []
    for url in URLS:
        html = requests.get(url).text
        soup = BeautifulSoup(html, "html.parser")
        # Use simple separator and strip whitespace
        text = soup.get_text(separator="\n", strip=True)
        # Collapse multiple newlines into one
        clean_text = re.sub(r'\n+', '\n', text)
        texts.append(clean_text)
    return "\n\n".join(texts)

if __name__ == "__main__":
    text = scrape()
    import os
    # Get the directory of the current script (backend/)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up one level to the project root
    project_root = os.path.dirname(current_dir)
    # Construct absolute path to data/site.txt
    data_path = os.path.join(project_root, "data", "site.txt")
    
    # Ensure data directory exists
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    
    with open(data_path, "w") as f:
        f.write(text)
