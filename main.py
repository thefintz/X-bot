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
    
    # Carregar links antigos
    try:
        with open("view_links.json", "r") as file:
            old_links = json.load(file)
    except FileNotFoundError:
        old_links = []

    # Adicionar apenas novos links e atualizar o arquivo view_links.json
    new_links = [link for link in view_links if link not in old_links]
    if new_links: # verificar se nao esta vazio
        view_links = old_links + new_links  # Atualiza view_links com todos os links ja encontrados
        with open("view_links.json", "w") as outfile: # abrimos view_links.json e gravamos view_links dentro dele usando json.dump
            json.dump(view_links, outfile, indent=4, ensure_ascii=False)
        print(f"{len(new_links)} novos links adicionados.")
    else:
        print("Nenhum link novo encontrado.")

    return new_links

def post_tweets(new_links):
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    bearer_token = os.getenv("BEARER_TOKEN")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

    client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)

    # Carrega historico completo de links ja postados
    try:
        with open("last_posted.json", "r") as file:
            posted_links = json.load(file)
        print("Historico de links postados carregado:", posted_links)
    except FileNotFoundError:
        posted_links = []
        print("Arquivo last_posted.json nao encontrado; inicializando como lista vazia.")

    # Se nao houver novos links para postar, termina a funcao sem erro
    if not new_links:
        print("Nao ha novos links para serem postados.")
        return

    # Posta apenas os links novos
    for link_to_post in new_links:
        print(f"Postando tweet: {link_to_post}")
        try:
            client.create_tweet(text=f"Link do documento: {link_to_post}")
            print(f"Tweet postado: {link_to_post}")
        except tweepy.errors.Forbidden:
            print(f"Tweet duplicado detectado e ignorado: {link_to_post}")
            continue

        # Atualiza o historico com o novo link postado
        posted_links.append(link_to_post)
        with open("last_posted.json", "w") as file:
            json.dump(posted_links, file, indent=4, ensure_ascii=False)
        print("Historico atualizado:", posted_links)

        time.sleep(60)

# Executa as funcoes
new_links = fetch_links()
post_tweets(new_links)
