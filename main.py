import requests
import json
import time
import tweepy
import os
import re

def fetch_links():
    url = "https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx/ListarDocumentos"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    data = {
        "dataDe": "",
        "dataAte": "",
        "empresa": "",
        "setorAtividade": "-1",
        "categoriaEmissor": "-1",
        "situacaoEmissor": "-1",
        "tipoParticipante": "1,2,8",
        "dataReferencia": "",
        "categoria": "IPE_3_84_-1",
        "periodo": "1",
        "horaIni": "",
        "horaFim": "",
        "palavraChave": "",
        "ultimaDtRef": "false",
        "tipoEmpresa": "1",
        "token": "",
        "versaoCaptcha": ""
    }

    response = requests.post(url, headers=headers, json=data)
    
    with open("response.json", "w") as outfile:
        json.dump(response.json(), outfile, ensure_ascii=False, indent=4)
    
    # Extrai links do arquivo view_links.json
    with open("response.json", "r") as file:
        data = json.load(file)
        dados = data["d"]["dados"]
        view_links = re.findall(r"OpenPopUpVer\('([^']+)'\)", dados)
        view_links = [f"https://www.rad.cvm.gov.br/ENET/{link}" for link in view_links]
        
    with open("view_links.json", "w") as outfile:
        json.dump(view_links, outfile, indent=4, ensure_ascii=False)


def post_tweets():
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    bearer_token = os.getenv("BEARER_TOKEN")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

    client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)

    # le os links do arquivo json
    with open("view_links.json", "r") as file:
        links = json.load(file)

    # carrega indicie do ultimo link q foi postado
    try:
        with open("last_posted.json", "r") as file:
            last_posted = json.load(file)["last_index"]
    except FileNotFoundError:
        last_posted = -1 # comeca com primeiro link se n tiver ainda

    for i in range(last_posted + 1, len(links)):
        link_to_post = links[i]
        client.create_tweet(text=f"Link do documento: {link_to_post}")
        print(f"Tweet postado: {link_to_post}")

        # atualiza indice do ultimo link postado
        with open("last_posted.json", "w") as file:
            json.dump({"last_index": i}, file)
        
        time.sleep(60)

fetch_links()
post_tweets()
