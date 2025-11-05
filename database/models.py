from sqlalchemy import Column, Integer, String, ForeignKey, Date
from typing import List
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class EntidadeEmpresa(Base):
    __tablename__ = 'entidade_empresa'

    id_empresa = Column(Integer, primary_key=True, index=True)
    nm_fantasia = Column(String(100))
    rep_legal = Column(String(100))
    razao_social = Column(String(100), nullable=False)
    cnpj = Column(String(14), nullable=False)
    cidade = Column(String(100))

    
class Documento(Base):
    __tablename__ = 'documento'

    id_doc = Column(Integer, primary_key=True, index=True)
    id_empresa = Column(Integer, ForeignKey("entidade_empresa.id_empresa"))
    nm_arquivo = Column(String(100), nullable=False)
    nr_lote = Column(Integer)
    emissao_doc = Column(Date)
    tipo_doc = Column(String(100))


class PrtEnvolvida(Base):
    __tablename__ = 'prt_envolvida'

    id_prt = Column(Integer, primary_key=True, index=True)
    empresa_assoc = Column(String(100))
    titular = Column(String(100))

class CpfCnpj(Base):
    __tablename__ = 'cpf_cnpj'

    id_pjpf = Column(Integer, primary_key=True, index=True)
    CPF = Column(String(50))
    CNPJ = Column(String(50))

class DocPrtEnvolvida(Base):
    __tablename__ = 'doc_prt_envolvida'

    id_doc = Column(Integer, ForeignKey('documento.id_doc'), primary_key=True)
    id_prt = Column(Integer, ForeignKey('prt_envolvida.id_prt'), primary_key=True)

class DocPfpj(Base):
    __tablename__ = 'doc_pf_pj'

    id_doc = Column(Integer, ForeignKey('documento.id_doc'), primary_key=True)
    id_pjpf = Column(Integer, ForeignKey('cpf_cnpj.id_pjpf'), primary_key=True)


