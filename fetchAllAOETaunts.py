import requests
#import urllib
from bs4 import BeautifulSoup
import re

URL = "https://ageofempires.fandom.com/wiki/Taunts"
page = requests.get(URL)

soup = BeautifulSoup(page.content, "html.parser")
results = soup.find(id="mw-content-text")
tables = results.find_all("table", class_="article-table")
ii = 0
for table in tables:

    if ii == 2 or ii == 3:
        sounds = table.find_all("tr")
        for sound in sounds:
            parts = sound.find_all("td")
            filename = ""
            i = 0
            for part in parts:
                if i == 0:
                    filename  = str(part.renderContents().strip())[2:-1]
                elif i == 1:
                    filename += "_" + str(part.renderContents().strip())[2:-1]
                elif i == 2:
                    span = part.find("span", class_="audio-button")
                    filename = re.sub(r'\W+', '', filename)
                    print(filename)
                    r = requests.get(span['data-src'], allow_redirects=True)
                    open(filename + '.ogg', 'wb').write(r.content)
                i += 1
    ii+=1