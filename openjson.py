import json
import re

# abre json gerado por testcurl.py -> response.json
with open("response.json", "r") as file:
    data = json.load(file)

# extrai o campo dados
dados = data["d"]["dados"]

# expressao regular p pegar os links dos arquivos 
view_links = re.findall(r"OpenPopUpVer\('([^']+)'\)", dados)

# adiciona os dominios pois a parte acima so contem o conteudo especifico de cada link mas falta o dominio
view_links = [f"https://www.rad.cvm.gov.br/ENET/{link}" for link in view_links]

# salva links em json
with open("links.json", "w") as outfile:
    json.dump(view_links, outfile, indent=4, ensure_ascii=False)