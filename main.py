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

    # Adicionar apenas novos links
    new_links = [link for link in view_links if link not in old_links]
    
    # Se houver novos links, atualiza o arquivo view_links.json
    if new_links:
        all_links = old_links + new_links
        with open("view_links.json", "w") as outfile:
            json.dump(all_links, outfile, indent=4, ensure_ascii=False)
    else:
        print("Nenhum link novo encontrado.")


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

    # se nao tiver links novos, termina a funcao
    if not links:
        print("Nenhum link novo para postar.")
        return

    # carrega indice do ultimo link que foi postado
    try:
        with open("last_posted.json", "r") as file:
            last_posted = json.load(file)["last_index"]
    except FileNotFoundError:
        last_posted = -1  # comeca com primeiro link se n tiver ainda

    # posta apenas os links novos
    for i in range(last_posted + 1, len(links)):
        link_to_post = links[i]

        # Verifica se já foi postado
        try:
            client.create_tweet(text=f"Link do documento: {link_to_post}")
            print(f"Tweet postado: {link_to_post}")

            # atualiza indice do ultimo link postado
            with open("last_posted.json", "w") as file:
                json.dump({"last_index": i}, file)

            time.sleep(60)
            
        except tweepy.errors.Forbidden as e:
            print(f"Erro ao postar: {e}")
            if "You are not allowed to create a Tweet with duplicate content" in str(e):
                # Salva o índice para evitar tentativa futura
                with open("last_posted.json", "w") as file:
                    json.dump({"last_index": i}, file)
            else:
                raise e  # levanta erro se for diferente

fetch_links()
post_tweets()
