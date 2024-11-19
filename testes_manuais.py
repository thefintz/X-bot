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
    data_com: str
    data_ex: str
    data_pagamento: str

class OpenAiResponse(BaseModel):
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
            {
            "role": "system",
            "content": (
                "Você é um especialista em análise de documentos financeiros de empresas. "
                "Sua tarefa é identificar se o conteúdo do trecho analisado menciona o pagamento atual de proventos, bonificações, dividendos ou juros sobre capital próprio. "
                "Se o trecho abordar apenas menções a direitos futuros, como 'as novas ações terão direito a dividendos ou juros sobre capital próprio após um evento específico', ele não deve ser classificado como relacionado a proventos. "
                "Classifique como 'Sim' e retorne True somente se o documento tratar diretamente de um pagamento de proventos ou eventos associados a um pagamento efetivo. Caso contrário, classifique como 'Não' e retorne False. "
                "Além disso, se o trecho mencionar um pagamento efetivo de proventos, extraia exclusivamente as informações presentes no documento, sem criar ou supor dados ausentes. "
                "Procure os seguintes dados no documento: ticker, valor pago por ação, tipo de provento (por exemplo, dividendos, juros sobre capital próprio), tipo de ação (ON, PN, Unit), data 'com', data 'ex', data de pagamento e nome da empresa. "
                "Ao identificar valores de proventos, preste atenção especial para diferenciar entre: "
                "- Valores totais que representam a soma de múltiplos proventos (exemplo: 'R$ 0,41241470179 por ação, representando a soma de R$ 0,10540623892 e R$ 0,30700846287'). "
                "- Proventos específicos com valores discriminados individualmente para diferentes tipos de ações. Por exemplo, um documento que descreva valores por ação ordinária, preferencial e UNITs deve ser interpretado como três proventos distintos, com cada um vinculado ao seu respectivo tipo de ação. "
                "Certifique-se de identificar cada provento individualmente, mesmo que estejam vinculados a um único evento de declaração ou pagamento. "
                "Ao identificar a **data com**, procure trechos que descrevam a posição acionária utilizada como base para o pagamento do provento. Isso pode ser indicado explicitamente por termos como 'posição acionária constante nos registros', 'posição ao final de', ou, em tabelas e documentos formais, termos alternativos como 'base de pagamento' ou 'data de base'. "
                "Ao identificar a **data ex**, busque expressões como 'ações serão negociadas ex-dividendos a partir de', 'negociação ex-direito' ou outros termos semelhantes. "
                "Retorne as datas no formato dd/mm/yyyy e o valor em formato decimal (por exemplo, 'R$ 0,50 por ação' deve ser extraído como 0.50). "
                "Se alguma informação, como ticker, valor por ação, tipo de provento, tipo de ação, data 'com', data 'ex', data de pagamento ou nome da empresa, não estiver explicitamente mencionada no documento, retorne 'NA' para esses campos. "
                "Certifique-se de classificar corretamente apenas pagamentos atuais de proventos, evitando confusões com valores totais, aumento de capital social, direitos futuros ou descrições gerais sobre possíveis proventos associados a novos ativos."
            )
            },
            {
            "role": "user",
            "content": f"Este trecho menciona pagamento atual de proventos? {parte}."
            }
        ],
        response_format=OpenAiResponse,
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
                f"Ticker: {provento.ticker}\n"
                f"Tipo de Provento: {provento.tipo_provento}\n"
                f"Tipo de acao: {provento.tipo_acao}\n"
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


# # teste com 20 docs do sheets
# link_teste = "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=822581&numVersao=1&numProtocolo=1297855&descTipo=IPE&CodigoInstituicao=1"
# resultado_teste = verificar_conteudo(link_teste)

# if resultado_teste:
#     empresa = resultado_teste["empresa"]
#     proventos = resultado_teste["proventos"]
#     for provento in proventos:
#         tweet_content = (
#             f"Empresa: {empresa}\n"
#             f"Ticker: {provento.ticker}\n"
#             f"Tipo de Provento: {provento.tipo_provento}\n"
#             f"Tipo de acao: {provento.tipo_acao}\n"
#             f"Valor por Ação: R$ {provento.valor}\n"
#             f"DataCom: {provento.data_com}\n"
#             f"DataEx: {provento.data_ex}\n"
#             f"Data de Pagamento: {provento.data_pagamento}\n"
#             f"Veja o documento: {link_teste}"
#         )
#         print(tweet_content)
# else:
#     print("Nenhum conteúdo relacionado a proventos foi encontrado.")
