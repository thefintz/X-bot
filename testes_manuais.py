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
    
    # pega os links de download do arquivo view_links.json
    with open("response_download.json", "r") as file:
        data = json.load(file)
        dados = data["d"]["dados"] # regex: localizamos a funcao opendownloaddocumentos e os 3 parametros p montar a url(numSequencia, numVersao, numProtocolo)
        view_links = re.findall(r"OpenDownloadDocumentos\('(\d+)',\s*'(\d+)',\s*'(\d+)',\s*'IPE'\)", dados)
        view_links = [
            f"https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia={match[0]}&numVersao={match[1]}&numProtocolo={match[2]}&descTipo=IPE&CodigoInstituicao=1"
            for match in view_links]

    # Carregar links antigos
    try:
        with open("last_posted_download.json", "r") as file:
            last_posted = json.load(file)
    except FileNotFoundError:
        last_posted = []

    # Adicionar apenas novos links e atualizar o arquivo view_links.json
    new_links = [link for link in view_links if link not in last_posted]
    if new_links: # verificar se nao esta vazio
        view_links = last_posted + new_links  # Atualiza view_links com todos os links ja encontrados
        with open("view_links_download.json", "w") as outfile: # abrimos view_links.json e gravamos view_links dentro dele usando json.dump
            json.dump(view_links, outfile, indent=4, ensure_ascii=False)
        protocolo_ids = [f"id: {match.group(1)}" for link in new_links if (match := re.search(r'NumeroProtocoloEntrega=(\d+)', link))]
        print(f"{len(new_links)} novo(s) link(s)encontrado(s) e adicionado(s): {', '.join(protocolo_ids)}")
        print("\n")
    else:
        print("Nenhum link novo ou nenhum link novo relacionado a proventos foi encontrado.")

    return new_links

class get_openai_response(BaseModel):
    proventos: bool
    empresa: str
    ticker: list[str]
    # valor_por_ticker: float
    # valor_por_acao: float   -> mais comum nos documentos
    valor: list[float]
    tipo_provento: list[str]
    data_com: list[str]
    data_pagamento: list[str]

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

    if openai_response.proventos:
        return {"link": link_download,
                "empresa": openai_response.empresa,
                "valor": openai_response.valor,
                "tipo_provento": openai_response.tipo_provento,
                "data_com": openai_response.data_com,
                "data_pagamento": openai_response.data_pagamento}
    return None

def post_tweets(provento_links):
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")
    bearer_token = os.getenv("BEARER_TOKEN")
    access_token = os.getenv("ACCESS_TOKEN")
    access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

    client = tweepy.Client(bearer_token, api_key, api_secret, access_token, access_token_secret)

    try:
        with open("last_posted_download.json", "r") as file:
            posted_links = json.load(file)
    except FileNotFoundError:
        posted_links = []

    for info in provento_links:
        link_to_post = info["link"]
        empresa = info.get("empresa", "Empresa não identificada")
        valor = info.get("valor", "valor não informado")
        data_com = info.get("data_com", "data não informada")
        tweet_content = f"Boas notícias! A empresa {empresa} anunciou novos proventos no valor de R$ {valor} por ação com dataCom {data_com}. Confira o documento: {link_to_post}"
        try:
            # client.create_tweet(text=tweet_content)
            print(f"Tweet postado: {tweet_content}")
        except tweepy.errors.Forbidden:
            print(f"Tweet duplicado detectado e ignorado ou erro: {tweet_content}")
            continue

        # Atualiza o historico com o novo link postado
        posted_links.append(link_to_post)
        with open("last_posted_download.json", "w") as file:
            json.dump(posted_links, file, indent=4, ensure_ascii=False)
        print(f"Quantidade de links postados ao total: {len(posted_links)}")
        # time.sleep(3)


new_links = fetch_links()

# Verifica o conteúdo dos novos links e filtra aqueles relacionados a proventos
provento_links = [verificar_conteudo(link) for link in new_links]
provento_links = [info for info in provento_links if info]  # Remove entradas None

if provento_links:
    post_tweets(provento_links)
elif new_links:
    quantidade_nao_proventos = len(new_links) - len(provento_links)
    print(f"{quantidade_nao_proventos} novo(s) link(s) encontrado(s), mas nenhum deles trata de proventos.")
else:
    print("Não há novos links.")
