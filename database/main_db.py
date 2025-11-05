from config_conexao import conectar_banco, fechar_conexao


if __name__ == "__main__":
    conn = conectar_banco()
    if conn:
        print("Conexão ok!")
        fechar_conexao(conn)
    else:
        print("Falha na conexão")
''''
caminho_pdf = r'documentos\ARCIMOL - PRE MOLDADOS E CONSTRUTORA DE OBRAS LTDA - Contrato de Empresa Associada.pdf'
resultado = processar_pdf(caminho_pdf)
salvar_no_banco(resultado)

PASTA_PDFS = r'C:\Users\paoll\OneDrive\DOCS\BPK\proj\projeto_busca_juridico\documentos'
resultado = processar_pasta(PASTA_PDFS, limite=20)
salvar_no_banco(resultado)
'''