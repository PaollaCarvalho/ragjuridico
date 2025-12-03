"""
Redis Service - Gerenciamento de Cache de PDFs em Memória
Armazena PDFs temporariamente no Redis ao invés do disco
"""

import redis
import io
import os
from typing import Optional, Dict
from datetime import timedelta
from googleapiclient.http import MediaIoBaseDownload

# Configurações do Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)

# TTL (Time To Live) - tempo em segundos que o arquivo fica em cache
PDF_CACHE_TTL = 3600  # 1 hora
METADATA_CACHE_TTL = 7200  # 2 horas

class RedisService:
    """Serviço para gerenciar cache de PDFs e metadados no Redis"""
    
    def __init__(self):
        """Inicializa conexão com Redis"""
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=False  # Importante para dados binários (PDFs)
            )
            # Testa conexão
            self.redis_client.ping()
            print(f"✅ Conectado ao Redis em {REDIS_HOST}:{REDIS_PORT}")
        except redis.ConnectionError as e:
            print(f"❌ Erro ao conectar ao Redis: {e}")
            raise
    
    # ========================================
    # CACHE DE PDFs (BINÁRIO)
    # ========================================
    
    def salvar_pdf(self, doc_id: int, pdf_bytes: bytes, ttl: int = PDF_CACHE_TTL) -> bool:
        """
        Salva PDF no Redis como bytes
        
        Args:
            doc_id: ID do documento no banco de dados
            pdf_bytes: Bytes do arquivo PDF
            ttl: Tempo de vida em segundos (padrão: 1 hora)
            
        Returns:
            True se salvou com sucesso
        """
        try:
            key = f"pdf:{doc_id}"
            self.redis_client.setex(
                name=key,
                time=ttl,
                value=pdf_bytes
            )
            print(f"📄 PDF {doc_id} armazenado em cache ({len(pdf_bytes)} bytes)")
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar PDF no Redis: {e}")
            return False
    
    def obter_pdf(self, doc_id: int) -> Optional[bytes]:
        """
        Recupera PDF do Redis
        
        Args:
            doc_id: ID do documento
            
        Returns:
            Bytes do PDF ou None se não encontrado
        """
        try:
            key = f"pdf:{doc_id}"
            pdf_bytes = self.redis_client.get(key)
            
            if pdf_bytes:
                print(f"✅ PDF {doc_id} recuperado do cache")
                # Renova o TTL quando acessado
                self.redis_client.expire(key, PDF_CACHE_TTL)
                return pdf_bytes
            else:
                print(f"⚠️ PDF {doc_id} não encontrado no cache")
                return None
        except Exception as e:
            print(f"❌ Erro ao obter PDF do Redis: {e}")
            return None
    
    def pdf_existe(self, doc_id: int) -> bool:
        """Verifica se PDF está em cache"""
        key = f"pdf:{doc_id}"
        return self.redis_client.exists(key) > 0
    
    # ========================================
    # CACHE DE METADADOS (JSON/STRING)
    # ========================================
    
    def salvar_metadados(self, doc_id: int, metadados: Dict, ttl: int = METADATA_CACHE_TTL) -> bool:
        """
        Salva metadados do documento no Redis
        
        Args:
            doc_id: ID do documento
            metadados: Dicionário com informações do documento
            ttl: Tempo de vida em segundos
            
        Returns:
            True se salvou com sucesso
        """
        try:
            import json
            key = f"meta:{doc_id}"
            
            # Serializa para JSON
            metadados_json = json.dumps(metadados, default=str)
            
            self.redis_client.setex(
                name=key,
                time=ttl,
                value=metadados_json
            )
            print(f"📋 Metadados {doc_id} armazenados em cache")
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar metadados no Redis: {e}")
            return False
    
    def obter_metadados(self, doc_id: int) -> Optional[Dict]:
        """
        Recupera metadados do Redis
        
        Args:
            doc_id: ID do documento
            
        Returns:
            Dicionário com metadados ou None
        """
        try:
            import json
            key = f"meta:{doc_id}"
            metadados_json = self.redis_client.get(key)
            
            if metadados_json:
                # Renova TTL
                self.redis_client.expire(key, METADATA_CACHE_TTL)
                
                # Desserializa JSON
                if isinstance(metadados_json, bytes):
                    metadados_json = metadados_json.decode('utf-8')
                    
                return json.loads(metadados_json)
            return None
        except Exception as e:
            print(f"❌ Erro ao obter metadados do Redis: {e}")
            return None
    
    # ========================================
    # DOWNLOAD DIRETO PARA REDIS (GOOGLE DRIVE)
    # ========================================
    
    def baixar_drive_para_redis(self, service, file_id: str, doc_id: int) -> bool:
        """
        Baixa arquivo do Google Drive diretamente para o Redis
        Sem salvar no disco
        
        Args:
            service: Objeto GoogleDrive service
            file_id: ID do arquivo no Google Drive
            doc_id: ID do documento no banco de dados
            
        Returns:
            True se baixou e salvou com sucesso
        """
        try:
            # 1. Busca metadados do arquivo
            metadata = service.files().get(fileId=file_id, fields="name,size,mimeType").execute()
            nome_arquivo = metadata.get("name")
            tamanho = int(metadata.get("size", 0))
            
            print(f"📥 Baixando {nome_arquivo} do Drive ({tamanho} bytes)...")
            
            # 2. Baixa para memória (BytesIO)
            request = service.files().get_media(fileId=file_id)
            file_bytes = io.BytesIO()
            downloader = MediaIoBaseDownload(file_bytes, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"   Download: {int(status.progress() * 100)}%")
            
            # 3. Salva PDF no Redis
            pdf_bytes = file_bytes.getvalue()
            sucesso_pdf = self.salvar_pdf(doc_id, pdf_bytes)
            
            # 4. Salva metadados no Redis
            metadados = {
                "nome_arquivo": nome_arquivo,
                "tamanho": tamanho,
                "mime_type": metadata.get("mimeType"),
                "drive_file_id": file_id
            }
            sucesso_meta = self.salvar_metadados(doc_id, metadados)
            
            print(f"✅ Arquivo baixado e armazenado em cache (Redis)")
            return sucesso_pdf and sucesso_meta
            
        except Exception as e:
            print(f"❌ Erro ao baixar do Drive para Redis: {e}")
            return False
    
    # ========================================
    # CONVERSÃO PARA ARQUIVO TEMPORÁRIO (COMPATIBILIDADE)
    # ========================================
    
    def obter_pdf_como_arquivo_temp(self, doc_id: int) -> Optional[str]:
        """
        Recupera PDF do Redis e salva temporariamente no disco
        Útil para compatibilidade com bibliotecas que precisam de arquivo físico
        
        Args:
            doc_id: ID do documento
            
        Returns:
            Caminho do arquivo temporário ou None
        """
        import tempfile
        
        pdf_bytes = self.obter_pdf(doc_id)
        
        if not pdf_bytes:
            return None
        
        try:
            # Busca metadados para pegar nome original
            metadados = self.obter_metadados(doc_id)
            nome_arquivo = metadados.get('nome_arquivo', f'doc_{doc_id}.pdf') if metadados else f'doc_{doc_id}.pdf'
            
            # Cria arquivo temporário
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"redis_cache_{doc_id}_{nome_arquivo}")
            
            # Escreve bytes
            with open(temp_path, 'wb') as f:
                f.write(pdf_bytes)
            
            print(f"💾 PDF temporário criado: {temp_path}")
            return temp_path
            
        except Exception as e:
            print(f"❌ Erro ao criar arquivo temporário: {e}")
            return None
    
    # ========================================
    # GERENCIAMENTO DE CACHE
    # ========================================
    
    def limpar_documento(self, doc_id: int) -> bool:
        """Remove PDF e metadados do cache"""
        try:
            pdf_key = f"pdf:{doc_id}"
            meta_key = f"meta:{doc_id}"
            
            deleted_pdf = self.redis_client.delete(pdf_key)
            deleted_meta = self.redis_client.delete(meta_key)
            
            print(f"🗑️ Documento {doc_id} removido do cache")
            return (deleted_pdf + deleted_meta) > 0
        except Exception as e:
            print(f"❌ Erro ao limpar cache: {e}")
            return False
    
    def limpar_todos(self) -> int:
        """
        Limpa todos os PDFs e metadados do cache
        
        Returns:
            Número de chaves deletadas
        """
        try:
            # Busca todas as chaves de PDF e metadados
            pdf_keys = self.redis_client.keys("pdf:*")
            meta_keys = self.redis_client.keys("meta:*")
            
            all_keys = pdf_keys + meta_keys
            
            if all_keys:
                deleted = self.redis_client.delete(*all_keys)
                print(f"🗑️ Cache limpo: {deleted} documentos removidos")
                return deleted
            return 0
        except Exception as e:
            print(f"❌ Erro ao limpar cache completo: {e}")
            return 0
    
    def info_cache(self) -> Dict:
        """Retorna informações sobre o cache"""
        try:
            info = self.redis_client.info('memory')
            
            pdf_keys = len(self.redis_client.keys("pdf:*"))
            meta_keys = len(self.redis_client.keys("meta:*"))
            
            return {
                "pdfs_em_cache": pdf_keys,
                "metadados_em_cache": meta_keys,
                "memoria_usada_mb": round(info['used_memory'] / (1024 * 1024), 2),
                "memoria_pico_mb": round(info['used_memory_peak'] / (1024 * 1024), 2),
            }
        except Exception as e:
            print(f"❌ Erro ao obter info do cache: {e}")
            return {}
    
    def renovar_ttl(self, doc_id: int, ttl: int = PDF_CACHE_TTL) -> bool:
        """Renova o tempo de vida de um documento no cache"""
        try:
            pdf_key = f"pdf:{doc_id}"
            meta_key = f"meta:{doc_id}"
            
            self.redis_client.expire(pdf_key, ttl)
            self.redis_client.expire(meta_key, ttl)
            
            print(f"⏰ TTL renovado para documento {doc_id}")
            return True
        except Exception as e:
            print(f"❌ Erro ao renovar TTL: {e}")
            return False


# ========================================
# INSTÂNCIA GLOBAL DO SERVIÇO
# ========================================
_redis_service_instance = None

def get_redis_service() -> RedisService:
    """
    Retorna instância única do RedisService (Singleton)
    Cria apenas na primeira vez que for chamado
    """
    global _redis_service_instance
    
    if _redis_service_instance is None:
        _redis_service_instance = RedisService()
    
    return _redis_service_instance