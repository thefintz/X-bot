import requests
import json
import time
import tweepy
import os
import re

# Parte 1: Coleta dos links da CVM e salva em view_links.json
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
    
    # Extrai links de view_links.json
    with open("response.json", "r") as file:
        data = json.load(file)
        dados = data["d"]["dados"]
        view_links = re.findall(r"OpenPopUpVer\('([^']+)'\)", dados)
        view_links = [f"https://www.rad.cvm.gov.br/ENET/{link}" for link in view_links]
        
    with open("view_links.json", "w") as outfile:
        json.dump(view_links, outfile, indent=4, ensure_ascii=False)

# Parte 2: Publicação no X com intervalo de tempo
def post_tweets():
    # Configuração da API do Twitter
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    api = tweepy.API(auth)

    # Lê os links do JSON
    with open("view_links.json", "r") as file:
        links = json.load(file)

    # Carrega o índice do último link postado
    try:
        with open("last_posted.json", "r") as file:
            last_posted = json.load(file)["last_index"]
    except FileNotFoundError:
        last_posted = -1  # Começa do primeiro link se o arquivo não existir

    # Publica os links com intervalo de 1 minuto entre eles
    for i in range(last_posted + 1, len(links)):
        link_to_post = links[i]
        api.update_status(f"Confira o documento: {link_to_post}")
        print(f"Tweet postado: {link_to_post}")

        # Atualiza o índice do último link postado
        with open("last_posted.json", "w") as file:
            json.dump({"last_index": i}, file)
        
        time.sleep(60)  # Espera 1 minuto antes de postar o próximo link

# Executa a coleta e depois a postagem
fetch_links()
post_tweets()
