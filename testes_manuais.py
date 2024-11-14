import os
import requests
import openai
import fitz
from dotenv import load_dotenv
from pydantic import BaseModel
from openai import OpenAI
import json
import re
import tweepy
import time

client = OpenAI()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

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
    
    with open("response_download.json", "w") as outfile:
        json.dump(response.json(), outfile, ensure_ascii=False, indent=4)
    
    with open("response_download.json", "r") as file:
        data = json.load(file)
        dados = data["d"]["dados"]
        request_links = re.findall(r"OpenDownloadDocumentos\('(\d+)',\s*'(\d+)',\s*'(\d+)',\s*'IPE'\)", dados)
        request_links = [
            f"https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia={match[0]}&numVersao={match[1]}&numProtocolo={match[2]}&descTipo=IPE&CodigoInstituicao=1"
            for match in request_links]

    try:
        with open("view_links_download.json", "r") as file:
            view_links = json.load(file)
    except FileNotFoundError:
        view_links = []

    try:
        with open("last_posted_download.json", "r") as file:
            last_posted = json.load(file)
    except FileNotFoundError:
        last_posted = []

    new_links = [link for link in request_links if link not in view_links and link not in last_posted]

    if new_links:
        view_links.extend(new_links)

        with open("view_links_download.json", "w") as outfile:
            json.dump(view_links, outfile, indent=4, ensure_ascii=False)

        protocolo_ids = [f"id: {match.group(1)}" for link in new_links if (match := re.search(r'numProtocolo=(\d+)', link))]
        print(f"{len(new_links)} novo(s) link(s) encontrado(s) e adicionado(s): {', '.join(protocolo_ids)}\n")
    else:
        print("Nenhum link novo ou nenhum link novo relacionado a proventos foi encontrado.")

    return new_links

class Provento(BaseModel):
    ticker: str
    valor: float
    tipo_provento: str
    tipo_acao: str
    data_com: str # testar data_com tipo date. prompt retorne data formato dd/mm/yyyy
    data_ex: str
    data_pagamento: str

class get_openai_response(BaseModel):
    is_provento: bool
    empresa: str
    proventos: list[Provento]


def verificar_conteudo(link_download):
    print(f"processando conteudo do link: {link_download}")
    response = requests.get(link_download)
    response.raise_for_status()
    
    with open("temp.pdf", "wb") as f:
        f.write(response.content)
    
    conteudo = ""
    with fitz.open("temp.pdf") as pdf:
        for page in pdf:
            conteudo += page.get_text()
    
    os.remove("temp.pdf")
    
    parte = conteudo[:10000]
    
    encontrou_proventos = False

    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Você é um especialista que analisa documentos financeiros de empresas. "
                "Retorne True se o trecho analisado se referir a pagamento de proventos, bonificações, dividendos ou juros sobre capital próprio; caso contrário, retorne False."
                "Ou seja, se em qualquer momento o documento falar sobre pagamento de algum tipo de provento ou algo do tipo juros sobre capital próprio, dividendos, proventos, pagamento por ação, classifique esse documento como 'Sim' para de proventos e retorne True, caso contrário, como 'Não' e False."
                "Se o documento tratar de proventos, extraia também o valor pago por ação e a dataCom."
                "Por exemplo, se o documento menciona algo como 'R$ 0,50 por ação', você deve retornar 0.50 como valor.")},
            {"role": "user", "content": f"Este trecho fala sobre proventos? {parte}."}
        ],
        response_format=get_openai_response,
    )

    openai_response = completion.choices[0].message.parsed
    print(openai_response)
    print("\n")
    print("-" * 20)

    if openai_response.is_provento:
        return {
            "link": link_download,
            "empresa": openai_response.empresa,
            "proventos": openai_response.proventos  # Lista de objetos Provento
        }
    return None

def post_tweets(provento_links):
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    bearer_token = os.getenv("BEARER_TOKEN")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

    client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)

    # Carregar ou inicializar o controle de duplicação
    try:
        with open("last_posted_download.json", "r") as file:
            posted_links = json.load(file)
    except FileNotFoundError:
        posted_links = []

    for info in provento_links:
        link_to_post = info["link"]
        empresa = info["empresa"]
        proventos = info["proventos"]

        # Verifica se o link já foi postado
        if link_to_post in posted_links:
            print(f"O link {link_to_post} já foi postado anteriormente.")
            continue

        # Postar todos os proventos do link, pois este ainda não foi postado
        for provento in proventos:
            tweet_content = (
                f"Empresa: {empresa}\n"
                f"Tipo de Provento: {provento.tipo_provento}\n"
                f"Valor por Ação: R$ {provento.valor}\n"
                f"DataCom: {provento.data_com}\n"
                f"DataEx: {provento.data_ex}\n"
                f"Data de Pagamento: {provento.data_pagamento}\n"
                f"Veja o documento: {link_to_post}"
            )

            try:
                # client.create_tweet(text=tweet_content)  # Descomente esta linha para postar o tweet de verdade
                print(f"Tweet postado: {tweet_content}")
            except tweepy.errors.Forbidden:
                print(f"Tweet duplicado detectado e ignorado ou erro: {tweet_content}")
                continue

        # Adicionar o link ao arquivo JSON após postar todos os proventos do link
        posted_links.append(link_to_post)
        with open("last_posted_download.json", "w") as file:
            json.dump(posted_links, file, indent=4, ensure_ascii=False)
        print(f"Quantidade de links postados ao total: {len(posted_links)}")
        print("\n")
        # time.sleep(3)


new_links = fetch_links()

provento_links = []
for link in new_links:
    resultado = verificar_conteudo(link)
    if resultado:
        provento_links.append(resultado)

if provento_links:
    post_tweets(provento_links)
elif new_links:
    quantidade_nao_proventos = len(new_links) - len(provento_links)
    print(f"{quantidade_nao_proventos} novo(s) link(s) encontrado(s), mas nenhum deles trata de proventos.")