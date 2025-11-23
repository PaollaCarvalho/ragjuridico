import fitz  # PyMuPDF
import re as r
import os
from typing import List, Dict

def ler_pgsdoc(caminho_pdf, paginas):
    try:
        doc = fitz.open(caminho_pdf)

        if isinstance(paginas, int):
            paginas = [paginas]

        read = [doc[pagina].get_text() for pagina in paginas]
        return read
    except Exception as e:
        print(f"Erro p ler {caminho_pdf}: {e}")
        return None 
        

cpf_regex = r.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
cnpj_regex = r.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")

CPF_CNPJ_IGNORAR = {
    'cpf': ['047.139.439-40', '007.187.289-20', '009.108.355-94'],
    'cnpj': ['21.526.709/0001-03', '30.694.272/0001-08']
}

EMPRESAS_IGNORAR = [
    'PARQUE CIENTÍFICO E TECNOLÓGICO DE BIOCIÊNCIAS LTDA',
    'BIOPARK',
    'PARQUE CIENTIFICO E TECNOLOGICO DE BIOCIENCIAS LTDA'  # versão sem acento
]

MESES = {
    'janeiro': '01', 'fevereiro': '02', 'março': '03', 'marco': '03',
    'abril': '04', 'maio': '05', 'junho': '06',
    'julho': '07', 'agosto': '08', 'setembro': '09',
    'outubro': '10', 'novembro': '11', 'dezembro': '12'
}

def extrair_pfpj(caminho_pdf):
    read_pg1 = ler_pgsdoc(caminho_pdf, paginas=[0])
    
    read_pg1 = read_pg1[0] 
    
    cpfs_encontrados = cpf_regex.findall(read_pg1)
    cnpjs_encontrados = cnpj_regex.findall(read_pg1)

    cpfs_unicos = list(set(cpfs_encontrados))
    cnpjs_unicos = list(set(cnpjs_encontrados))

    cpf_filtrados = [
        cpf for cpf in cpfs_unicos 
        if cpf not in CPF_CNPJ_IGNORAR['cpf']
    ]
    
    cnpj_filtrados = [
        cnpj for cnpj in cnpjs_unicos 
        if cnpj not in CPF_CNPJ_IGNORAR['cnpj']
    ]

    return {
        "cpf": cpf_filtrados,
        "cnpj": cnpj_filtrados,
    } 


def extrair_info_arquivo(caminho_pdf: str) -> Dict:

    nome_arquivo = os.path.splitext(os.path.basename(caminho_pdf))[0]
    partes = nome_arquivo.rsplit(' - ', 1)
    
    if len(partes) != 2:
        return {'empresas': [], 'tipo_documento': ''}
    
    parte_empresas = partes[0].strip()
    tipo_documento = partes[1].strip()
    
    # Verifica se tem múltiplas empresas (separadas por 'x' ou '&')
    separadores = r'\s+[xX]\s+'
    
    if r.search(separadores, parte_empresas):
        empresas = r.split(separadores, parte_empresas)
        empresas = [emp.strip() for emp in empresas]
    else:
        empresas = [parte_empresas.strip()]
    
    return {
        'empresas': empresas,
        'tipo_documento': tipo_documento
    }


def extrair_envolvidos(caminho_pdf: str, empresas_arquivo: List[str]) -> List[Dict[str, str]]:
  
    read_lastpg = ler_pgsdoc(caminho_pdf, paginas=[-1,-2,-3])
    texto_completo = '\n'.join(read_lastpg) if isinstance(read_lastpg, list) else read_lastpg
    
    resultado = []
    
    for empresa in empresas_arquivo:
        
        if any(biopark.upper() in empresa.upper() for biopark in EMPRESAS_IGNORAR):
            continue
        
       
        linhas = texto_completo.split('\n')
        
        for i, linha in enumerate(linhas):
            linha_upper = linha.upper().strip()
            empresa_upper = empresa.upper().strip()
            
            # Normaliza para comparação (remove pontuação extra)
            linha_normalizada = r.sub(r'[^\w\s]', ' ', linha_upper)
            empresa_normalizada = r.sub(r'[^\w\s]', ' ', empresa_upper)
            
            # Verifica se a linha contém a empresa
            # Permite match parcial das primeiras palavras-chave principais
            palavras_empresa = [p for p in empresa_normalizada.split() if len(p) > 2][:5]
            
            if len(palavras_empresa) >= 1:
                # Verifica se pelo menos as 2-3 primeiras palavras aparecem na linha
                match_palavras = sum(1 for p in palavras_empresa if p in linha_normalizada)
                
                if match_palavras >= 1:  # Pelo menos 2 palavras batem
                    
                    # Procura nas próximas 5 linhas pelo representante
                    for j in range(1, 6):  # Aumentei para 5 linhas
                        if i + j >= len(linhas):
                            break
                        
                        proxima_linha = linhas[i + j].strip()
                        
                        if not proxima_linha or len(proxima_linha) < 5:
                            continue
                        if r.search(r'\d{2,3}[\.\s]?\d{3}[\.\s]?\d{3}[-/\s]?\d{2,4}[-\s]?\d{2}', proxima_linha):
                            continue
                        if r.search(r'\bEMPRESA\s+ASSOCIADA\b', proxima_linha.upper()):
                            continue
                        if any(bio in proxima_linha.upper() for bio in ['BIOPARK', 'PARQUE CIENTIFICO', 'BIOCIENCIAS']):
                            continue
                        
                        match_nome = r.match(
                        r'^[A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][a-zà-úçãõâêôáéíóú]+(?:\s+(?:[A-ZÀÁÂÃÇÉÊÍÓÔÕÚ][a-zà-úçãõâêôáéíóú]+|de|da|do|dos|das|e)){1,6}$',
                        proxima_linha
                    )
                        
                        if match_nome:
                            # Valida que tem pelo menos nome e sobrenome
                            palavras_nome = proxima_linha.split()
                            
                            if len(palavras_nome) >= 2:  # Pelo menos 2 palavras (nome + sobrenome)
                                # Validações finais
                                invalidos = ['Empresa Associada', 'As Partes', 'De Biociencias', 
                                           'E Tecnologico', 'Victor Donaduzzi']
                                
                                if not any(inv.lower() in proxima_linha.lower() for inv in invalidos):
                                    resultado.append({
                                        'razao_social': empresa,
                                        'representante': proxima_linha
                                    })
                                    break  
                    
                    break  
    
    return resultado


def extrair_data(caminho_pdf):
    
    read_lastpg = ler_pgsdoc(caminho_pdf, paginas=[-4, -3, -2, -1])
    texto = ' '.join(read_lastpg) if isinstance(read_lastpg, list) else read_lastpg
    
    
    data_regex = r'Toledo/PR,?\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
    
    match = r.search(data_regex, texto, r.IGNORECASE | r.DOTALL)
    if match:
        dia, mes_nome, ano = match.groups()
        mes = MESES.get(mes_nome.lower())
        if mes:
            return f"{ano}-{mes}-{dia.zfill(2)}"
    
    return None
