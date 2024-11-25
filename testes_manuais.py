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

# autent X
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
CONSUMER_KEY = os.getenv("API_KEY")
CONSUMER_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET")

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

def load_json(file_path):
    with open(file_path, "r") as file:
        return json.load(file)

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

    view_links = load_json("view_links_download.json")
    last_posted = load_json("last_posted_download.json")

    new_links = [link for link in request_links if link not in view_links and link not in last_posted]

    if new_links:
        view_links.extend(new_links)
        save_json("view_links_download.json", view_links)

        protocolo_ids = [f"Protocolo: {match.group(1)}" for link in new_links if (match := re.search(r'numProtocolo=(\d+)', link))]
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

def analisar_documentos_openai(link_download):
    response = requests.get(link_download)
    response.raise_for_status()
    
    with open("temp.pdf", "wb") as f:
        f.write(response.content)
    
    conteudo = ""
    with fitz.open("temp.pdf") as pdf:
        for page in pdf:
            conteudo += page.get_text()
    os.remove("temp.pdf")
    
    texto_pdf = conteudo[:10_000] # dados sempre presentes nos 10000 primeiros tokens. obs: 4o mini aceita 128.000
    openai_response = get_openai_response(texto_pdf)
    print(openai_response)
    print("\n")

    return {"link": link_download, "empresa": openai_response.empresa, "proventos": openai_response.proventos, "is_provento": openai_response.is_provento}

def get_openai_response(texto_pdf):
    system_prompt = load_prompt("openai_prompt.txt")
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": texto_pdf}
        ],
        response_format=OpenAiResponse,
    )

    openai_response = completion.choices[0].message.parsed

    return openai_response

def post_tweets(provento_links):
    client = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        consumer_key=CONSUMER_KEY,
        consumer_secret=CONSUMER_SECRET,
        access_token=ACCESS_TOKEN,
        access_token_secret=ACCESS_TOKEN_SECRET,
    )

    posted_links = load_json("last_posted_download.json")

    for info in provento_links:
        link_to_post = info["link"]
        empresa = info["empresa"]
        proventos = info["proventos"]

        if link_to_post in posted_links:
            print(f"O link {link_to_post} já foi postado anteriormente.")
            continue

        if proventos:
            proventos_text = "\n".join(
                f"- {provento.tipo_provento} de R${provento.valor:.2f}".replace('.', ',')
                + f" (Data Com: {provento.data_com})"
                for provento in proventos
            )

            tweet_content = (
                f"🪙 {empresa} anunciou proventos:\n"
                f"{proventos_text}\n"
                f"🔗 Saiba mais: {link_to_post}"
            )

            try:
                client.create_tweet(text=tweet_content)
                print(f"Tweet postado: {tweet_content}")
            except tweepy.errors.Forbidden:
                print(f"Erro ou tweet duplicado ignorado: {tweet_content}")
                continue

            posted_links.append(link_to_post)
            save_json("last_posted_download.json", posted_links)
            print(f"Quantidade de links postados ao total: {len(posted_links)}\n")
            time.sleep(10)


# Fluxo Principal
new_links = fetch_links()

provento_links = []
for link in new_links:
    print(F"Processando link: {link}")
    resultado = analisar_documentos_openai(link)
    if resultado:
        provento_links.append(resultado)

if provento_links:
    post_tweets(provento_links)
elif new_links:
    quantidade_nao_proventos = len(new_links) - len(provento_links)
    print(f"{quantidade_nao_proventos} novo(s) link(s) encontrado(s), mas nenhum deles trata de proventos.")


# ================================
# teste com 20 documentos do sheets

# lista_de_links = ["https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=822534&numVersao=1&numProtocolo=1297808&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=822581&numVersao=1&numProtocolo=1297855&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823224&numVersao=1&numProtocolo=1298498&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823244&numVersao=1&numProtocolo=1298518&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823248&numVersao=1&numProtocolo=1298522&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823251&numVersao=1&numProtocolo=1298525&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823419&numVersao=1&numProtocolo=1298693&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823824&numVersao=1&numProtocolo=1299098&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823876&numVersao=1&numProtocolo=1299150&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823935&numVersao=1&numProtocolo=1299209&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823937&numVersao=1&numProtocolo=1299211&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823955&numVersao=1&numProtocolo=1299229&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=823961&numVersao=1&numProtocolo=1299235&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=824304&numVersao=1&numProtocolo=1299578&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=824963&numVersao=1&numProtocolo=1300237&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=825031&numVersao=1&numProtocolo=1300305&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=825097&numVersao=1&numProtocolo=1300371&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=825061&numVersao=1&numProtocolo=1300335&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=825037&numVersao=1&numProtocolo=1300311&descTipo=IPE&CodigoInstituicao=1",
# "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=824728&numVersao=1&numProtocolo=1300002&descTipo=IPE&CodigoInstituicao=1",
# ]


# resultados = []

# for link_teste in lista_de_links:
#     print(f"Processando link: {link_teste}")
#     resultado_teste = analisar_documentos_openai(link_teste)

#     if resultado_teste:
#         empresa = resultado_teste["empresa"]
#         proventos = resultado_teste.get("proventos", []) # extrai lista de proventos, se n tiver eh uma lista vazia
#         is_provento = resultado_teste["is_provento"]
        
#         if proventos:
#             for provento in proventos:
#                 resultados.append({
#                     # "DOCUMENTO": link_teste,
#                     "EMPRESA": empresa,
#                     "TICKER": provento.ticker,
#                     "IS_PROVENTO": is_provento,
#                     "DATA_COM": provento.data_com,
#                     "DATA_EX": provento.data_ex,
#                     "TIPO ACAO": provento.tipo_acao,
#                     "TIPO PROVENTO": provento.tipo_provento,
#                     "VALOR": provento.valor,
#                     "DATA_PAGAMENTO": provento.data_pagamento,
#                 })
#         else:  # Documento sem proventos
#             resultados.append({
#                 # "DOCUMENTO": link_teste,
#                 "EMPRESA": empresa,
#                 "TICKER": "N/A",
#                 "IS_PROVENTO": is_provento,
#                 "DATA_COM": "N/A",
#                 "DATA_EX": "N/A",
#                 "TIPO ACAO": "N/A",
#                 "TIPO PROVENTO": "N/A",
#                 "VALOR": "N/A",
#                 "DATA_PAGAMENTO": "N/A",
#             })
#     else:
#         print(f"Nenhum conteúdo foi retornado para o link: {link_teste}")

# if resultados:
#     df = pd.DataFrame(resultados, columns=[
#         "EMPRESA", "TICKER", "IS_PROVENTO", "DATA_COM", "DATA_EX", 
#         "TIPO ACAO", "TIPO PROVENTO", "VALOR", "DATA_PAGAMENTO"
#     ])
#     output_file = "resultados_proventos.csv"
#     df.to_csv(output_file, index=False, encoding="utf-8-sig")
#     print(f"Arquivo CSV gerado: {output_file}")
# else:
#     print("Nenhum dado de proventos foi encontrado nos links fornecidos.")

