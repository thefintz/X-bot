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

# Configuração do cliente OpenAI
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# Constantes
CVM_URL = "https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx/ListarDocumentos"
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "X-Requested-With": "XMLHttpRequest"
}
PAYLOAD = {
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

# Funções auxiliares para JSON
def load_json(file_path, default=None):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return default or []

def save_json(file_path, data):
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

# Carregar prompt do OpenAI
def load_prompt(file_path: str) -> str:
    with open(file_path, "r") as file:
        return file.read()

# Função principal para buscar links
def fetch_links():
    response = requests.post(CVM_URL, headers=HEADERS, json=PAYLOAD)
    response.raise_for_status()
    save_json("response_download.json", response.json())

    data = response.json()
    dados = data["d"]["dados"]
    request_links = re.findall(r"OpenDownloadDocumentos\('(\d+)',\s*'(\d+)',\s*'(\d+)',\s*'IPE'\)", dados)
    request_links = [
        f"https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia={match[0]}&numVersao={match[1]}&numProtocolo={match[2]}&descTipo=IPE&CodigoInstituicao=1"
        for match in request_links
    ]

    view_links = load_json("view_links_download.json", [])
    last_posted = load_json("last_posted_download.json", [])

    new_links = [link for link in request_links if link not in view_links and link not in last_posted]

    if new_links:
        view_links.extend(new_links)
        save_json("view_links_download.json", view_links)

        protocolo_ids = [f"id: {match.group(1)}" for link in new_links if (match := re.search(r'numProtocolo=(\d+)', link))]
        print(f"{len(new_links)} novo(s) link(s) encontrado(s): {', '.join(protocolo_ids)}")
    else:
        print("Nenhum link novo ou relevante encontrado.")

    return new_links

class Provento(BaseModel):
    ticker: str
    valor: float
    tipo_provento: str
    tipo_acao: str
    data_com: str
    data_ex: str
    data_pagamento: str

class OpenAiResponse(BaseModel):
    is_provento: bool
    empresa: str
    proventos: list[Provento]

def verificar_conteudo(link_download):
    prompt_content = load_prompt("openai_prompt.txt")
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
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt_content},
            {"role": "user", "content": f"Este trecho menciona pagamento atual de proventos? {parte}."}
        ],
        response_format=OpenAiResponse,
    )

    openai_response = completion.choices[0].message.parsed
    print(openai_response)
    print("\n")
    if openai_response.is_provento:
        return {"link": link_download, "empresa": openai_response.empresa, "proventos": openai_response.proventos}
    return None

def post_tweets(provento_links):
    client = tweepy.Client(
        bearer_token=os.getenv("BEARER_TOKEN"),
        consumer_key=os.getenv("API_KEY"),
        consumer_secret=os.getenv("API_SECRET"),
        access_token=os.getenv("ACCESS_TOKEN"),
        access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
    )

    posted_links = load_json("last_posted_download.json", [])

    for info in provento_links:
        link_to_post = info["link"]
        empresa = info["empresa"]
        proventos = info["proventos"]

        if link_to_post in posted_links:
            print(f"O link {link_to_post} já foi postado anteriormente.")
            continue

        for provento in proventos:
            tweet_content = (
                f"Empresa: {empresa}\n"
                f"Ticker: {provento.ticker}\n"
                f"Tipo de Provento: {provento.tipo_provento}\n"
                f"Tipo de ação: {provento.tipo_acao}\n"
                f"Valor por Ação: R$ {provento.valor}\n"
                f"DataCom: {provento.data_com}\n"
                f"DataEx: {provento.data_ex}\n"
                f"Data de Pagamento: {provento.data_pagamento}\n"
                f"Veja o documento: {link_to_post}"
            )

            try:
                # client.create_tweet(text=tweet_content)  # linha q faz o tweet
                print(f"Tweet postado: {tweet_content}")
            except tweepy.errors.Forbidden:
                print(f"Erro ou tweet duplicado ignorado: {tweet_content}")
                continue

        posted_links.append(link_to_post)
        save_json("last_posted_download.json", posted_links)
        print(f"Quantidade de links postados ao total: {len(posted_links)}\n")
        time.sleep(3)

# Fluxo Principal
# new_links = fetch_links()

# provento_links = []
# for link in new_links:
#     print(F"Processando link: {link}")
#     resultado = verificar_conteudo(link)
#     if resultado:
#         provento_links.append(resultado)

# if provento_links:
#     post_tweets(provento_links)
# elif new_links:
#     quantidade_nao_proventos = len(new_links) - len(provento_links)
#     print(f"{quantidade_nao_proventos} novo(s) link(s) encontrado(s), mas nenhum deles trata de proventos.")



# teste com 20 docs do sheets
link_teste = "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=822581&numVersao=1&numProtocolo=1297855&descTipo=IPE&CodigoInstituicao=1"
print(f"Processando link: {link_teste}")
resultado_teste = verificar_conteudo(link_teste)

if resultado_teste:
    empresa = resultado_teste["empresa"]
    proventos = resultado_teste["proventos"]
    for provento in proventos:
        tweet_content = (
            f"Empresa: {empresa}\n"
            f"Ticker: {provento.ticker}\n"
            f"Tipo de Provento: {provento.tipo_provento}\n"
            f"Tipo de acao: {provento.tipo_acao}\n"
            f"Valor por Ação: R$ {provento.valor}\n"
            f"DataCom: {provento.data_com}\n"
            f"DataEx: {provento.data_ex}\n"
            f"Data de Pagamento: {provento.data_pagamento}\n"
            f"Veja o documento: {link_teste}"
        )
        print(tweet_content)
else:
    print("Nenhum conteúdo relacionado a proventos foi encontrado.")