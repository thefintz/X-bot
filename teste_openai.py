import os
import requests
import openai
import fitz  # biblioteca q transforma o pdf em texto do jeito certo
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def verificar_conteudo(link_download):
    # fazer o download do arquivo
    response = requests.get(link_download)
    response.raise_for_status()
    
    # salvar o PDF temporariamente
    with open("temp.pdf", "wb") as f:
        f.write(response.content) #  ao inves de .text, .content mantem os dados em formatos de bytes
    
    # abrir o PDF e extrair o texto usando PyMuPDF
    conteudo = ""
    with fitz.open("temp.pdf") as pdf: # usamos a biblioteca p abrir nesse formato acima comentado ^
        for page in pdf:
            conteudo += page.get_text()  # Extrai o texto de cada página do PDF
    
    # remover o arquivo temporário
    os.remove("temp.pdf")
    
    # print(conteudo)
    partes = [conteudo[i:i+3000] for i in range(0, len(conteudo), 3000)]  # divide em partes de 3000 caracteres(openai limita os tokens)
                                                                          # esses tokens sao tipo palavras curtas ou pedacos de palavras
    encontrou_proventos = False

    for i, parte in enumerate(partes):
        resposta = openai.ChatCompletion.create(  # chama essa funcao e inicia conversa
            model="gpt-4o",
            messages=[
                {"role": "system", "content": (
                    "Você é um assistente que analisa documentos financeiros. "
                    "Classifique o trecho a seguir como 'Sim' ou 'Não' quanto ao fato de ele tratar de proventos de empresas, "
                    "como juros sobre capital próprio, dividendos, proventos, pagamento por ação."
                )},
                {"role": "user", "content": f"Este trecho fala sobre proventos? {parte}"}
            ]
        )
        conteudo_resposta = resposta['choices'][0]['message']['content'].strip().lower()  # so limpa o trecho

        if "sim" in conteudo_resposta:
            encontrou_proventos = True
            break

    if encontrou_proventos:
        print("Sim, o doc fala sobre proventos")
    else:
        print("Nao, o doc nao fala sobre proventos")

links = [
    "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=819427&numVersao=1&numProtocolo=1294701&descTipo=IPE&CodigoInstituicao=1",
    "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=819607&numVersao=2&numProtocolo=1294881&descTipo=IPE&CodigoInstituicao=1",
    "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=819634&numVersao=1&numProtocolo=1294908&descTipo=IPE&CodigoInstituicao=1",
    "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=819880&numVersao=1&numProtocolo=1295154&descTipo=IPE&CodigoInstituicao=1",
    "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx?Tela=ext&numSequencia=820117&numVersao=1&numProtocolo=1295391&descTipo=IPE&CodigoInstituicao=1"
]

for link in links:
    print(f"Processando link: {link}")
    verificar_conteudo(link)
    print("-" * 50)
