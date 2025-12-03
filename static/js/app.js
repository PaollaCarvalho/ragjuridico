// app.js - Sistema de Busca de Documentos com RAG

const API_BASE_URL = 'http://localhost:8000';

// ========================================
// FUNÇÕES DE BUSCA
// ========================================

async function buscarDocumentos() {
    const searchInput = document.getElementById('searchInput');
    const filterTipo = document.getElementById('filterTipo');
    const filterDataInicio = document.getElementById('filterDataInicio');
    const filterDataFim = document.getElementById('filterDataFim');
    
    const query = searchInput.value.trim();
    
    if (!query) {
        alert('Por favor, digite algo para buscar!');
        return;
    }
    
    // Mostra loading
    document.getElementById('loading').classList.add('active');
    document.getElementById('resultsSection').style.display = 'none';
    
    try {
        // Monta URL com filtros
        let url = `${API_BASE_URL}/buscar?q=${encodeURIComponent(query)}`;
        
        if (filterTipo.value) {
            url += `&tipo=${filterTipo.value}`;
        }
        if (filterDataInicio.value) {
            url += `&data_inicio=${filterDataInicio.value}`;
        }
        if (filterDataFim.value) {
            url += `&data_fim=${filterDataFim.value}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        // Esconde loading
        document.getElementById('loading').classList.remove('active');
        
        // Mostra resultados
        exibirResultados(data);
        
    } catch (error) {
        console.error('Erro na busca:', error);
        document.getElementById('loading').classList.remove('active');
        alert('Erro ao buscar documentos. Verifique se a API está rodando.');
    }
}

function exibirResultados(data) {
    const resultsSection = document.getElementById('resultsSection');
    const resultsGrid = document.getElementById('resultsGrid');
    const resultsCount = document.getElementById('resultsCount');
    const emptyState = document.getElementById('emptyState');
    
    resultsSection.style.display = 'block';
    
    if (data.documentos.length === 0) {
        resultsGrid.style.display = 'none';
        emptyState.style.display = 'flex';
        resultsCount.textContent = '0 documentos encontrados';
        return;
    }
    
    resultsGrid.style.display = 'grid';
    emptyState.style.display = 'none';
    resultsCount.textContent = `${data.total} documento(s) encontrado(s) em ${data.tempo_busca}s`;
    
    // Limpa resultados anteriores
    resultsGrid.innerHTML = '';
    
    // Cria cards
    data.documentos.forEach(doc => {
        const card = criarCardDocumento(doc);
        resultsGrid.appendChild(card);
    });
}

function criarCardDocumento(doc) {
    const card = document.createElement('div');
    card.className = 'doc-card';
    
    const envolvido = doc.envolvidos && doc.envolvidos[0] 
        ? doc.envolvidos[0] 
        : { empresa: 'N/A', representante: 'N/A' };
    
    const data = doc.data_assinatura 
        ? new Date(doc.data_assinatura).toLocaleDateString('pt-BR')
        : 'N/A';
    
    const cpf = doc.cpf_cnpj && doc.cpf_cnpj[0] && doc.cpf_cnpj[0].cpf 
        ? doc.cpf_cnpj[0].cpf 
        : null;
    
    const cnpj = doc.cpf_cnpj && doc.cpf_cnpj[0] && doc.cpf_cnpj[0].cnpj 
        ? doc.cpf_cnpj[0].cnpj 
        : null;
    
    const scorePercent = doc.score_relevancia || 0;
    
    card.innerHTML = `
        <div class="doc-header">
            <div class="doc-icon">📄</div>
            <div class="doc-header-text">
                <span class="doc-type">${doc.tipo_doc || 'Documento'}</span>
                <h3 class="doc-title">${doc.nome_arquivo || 'Sem título'}</h3>
                <p class="doc-date">📅 ${data}</p>
            </div>
        </div>
        
        <div class="doc-info">
            <div class="doc-info-item">
                <strong>Empresa:</strong>
                <span>${envolvido.empresa}</span>
            </div>
            <div class="doc-info-item">
                <strong>Representante:</strong>
                <span>${envolvido.representante}</span>
            </div>
            ${cpf ? `
                <div class="doc-info-item">
                    <strong>CPF:</strong>
                    <span>${cpf}</span>
                </div>
            ` : ''}
            ${cnpj ? `
                <div class="doc-info-item">
                    <strong>CNPJ:</strong>
                    <span>${cnpj}</span>
                </div>
            ` : ''}
        </div>
        
        <div class="progress-bar">
            <div class="progress-fill" style="width: ${scorePercent}%"></div>
        </div>
        
        <div style="display: flex; gap: 10px; margin-top: 15px;">
            <button 
                class="btn-primary btn-chat-rag" 
                data-doc-id="${doc.id_doc}"
                style="flex: 1; padding: 10px; font-size: 0.9rem;"
            >
                🤖 Chat RAG
            </button>
            <button 
                class="btn-primary btn-detalhes" 
                data-doc-id="${doc.id_doc}"
                style="flex: 1; padding: 10px; font-size: 0.9rem; background: var(--gradient-accent);"
            >
                📋 Detalhes
            </button>
        </div>
    `;
    
    // Adiciona event listeners após criar o card
    const btnChatRag = card.querySelector('.btn-chat-rag');
    const btnDetalhes = card.querySelector('.btn-detalhes');
    
    if (btnChatRag) {
        btnChatRag.addEventListener('click', (e) => {
            e.stopPropagation();
            abrirChatRAG(doc.id_doc);
        });
    }
    
    if (btnDetalhes) {
        btnDetalhes.addEventListener('click', (e) => {
            e.stopPropagation();
            verDetalhes(doc.id_doc);
        });
    }
    
    return card;
}

// ========================================
// NAVEGAÇÃO
// ========================================

async function abrirChatRAG(idDoc) {
    try {
        // Mostra indicador de loading
        const btnElement = event.target;
        const textoOriginal = btnElement.innerHTML;
        btnElement.disabled = true;
        btnElement.innerHTML = '⏳ Carregando...';
        
        // Faz cache do documento no Redis
        console.log('📥 Fazendo cache do documento', idDoc);
        
        const cacheResponse = await fetch(`${API_BASE_URL}/documento/${idDoc}/cache`, {
            method: 'POST'
        });
        
        if (cacheResponse.ok) {
            const cacheData = await cacheResponse.json();
            console.log('✅ Documento em cache:', cacheData);
        } else {
            console.warn('⚠️ Erro ao fazer cache, mas continuando...');
        }
        
        // Redireciona para Chat RAG
        window.location.href = `/busca-avancada?doc=${idDoc}`;
        
    } catch (error) {
        console.error('❌ Erro ao carregar documento:', error);
        alert('Erro ao carregar documento. Tente novamente.');
        
        // Restaura botão
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.innerHTML = textoOriginal;
        }
    }
}

async function verDetalhes(idDoc) {
    try {
        // Faz cache do documento antes de abrir modal
        console.log('📥 Fazendo cache do documento', idDoc);
        
        const cacheResponse = await fetch(`${API_BASE_URL}/documento/${idDoc}/cache`, {
            method: 'POST'
        });
        
        if (cacheResponse.ok) {
            const cacheData = await cacheResponse.json();
            console.log('✅ Documento em cache:', cacheData);
        }
        
        // Abre modal com detalhes
        abrirModal(idDoc);
        
    } catch (error) {
        console.error('❌ Erro ao fazer cache:', error);
        // Abre modal mesmo se cache falhar
        abrirModal(idDoc);
    }
}

// ========================================
// MODAL DE DETALHES
// ========================================

async function abrirModal(idDoc) {
    const modal = document.getElementById('documentModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalBody = document.getElementById('modalBody');
    
    modalTitle.textContent = 'Carregando...';
    modalBody.innerHTML = '<div style="text-align: center; padding: 40px;"><div class="spinner"></div><p>Carregando documento...</p></div>';
    
    modal.classList.add('active');
    
    try {
        const response = await fetch(`${API_BASE_URL}/documento/${idDoc}`);
        const doc = await response.json();
        
        modalTitle.textContent = doc.nome_arquivo;
        
        const envolvidos = doc.envolvidos.map(e => `
            <div class="doc-info-item">
                <strong>Empresa:</strong> ${e.empresa}<br>
                <strong>Representante:</strong> ${e.representante}
            </div>
        `).join('');
        
        const cpfCnpj = doc.cpf_cnpj.map(c => `
            <div class="doc-info-item">
                ${c.cpf ? `<div><strong>CPF:</strong> ${c.cpf}</div>` : ''}
                ${c.cnpj ? `<div><strong>CNPJ:</strong> ${c.cnpj}</div>` : ''}
                ${c.cpf2 ? `<div><strong>CPF 2:</strong> ${c.cpf2}</div>` : ''}
                ${c.cnpj2 ? `<div><strong>CNPJ 2:</strong> ${c.cnpj2}</div>` : ''}
            </div>
        `).join('');
        
        modalBody.innerHTML = `
            <div class="step-box">
                <h2>📋 Informações do Documento</h2>
                
                <div class="doc-info" style="margin-bottom: 20px;">
                    <div class="doc-info-item">
                        <strong>Tipo:</strong>
                        <span>${doc.tipo_doc || 'N/A'}</span>
                    </div>
                    <div class="doc-info-item">
                        <strong>Data de Assinatura:</strong>
                        <span>${doc.data_assinatura ? new Date(doc.data_assinatura).toLocaleDateString('pt-BR') : 'N/A'}</span>
                    </div>
                    <div class="doc-info-item">
                        <strong>Arquivo:</strong>
                        <span>${doc.nome_arquivo}</span>
                    </div>
                </div>
                
                <h3 style="margin-top: 20px; margin-bottom: 10px; color: var(--primary);">👥 Envolvidos</h3>
                <div class="doc-info">
                    ${envolvidos}
                </div>
                
                <h3 style="margin-top: 20px; margin-bottom: 10px; color: var(--primary);">🔢 CPF/CNPJ</h3>
                <div class="doc-info">
                    ${cpfCnpj}
                </div>
                
                <div style="margin-top: 30px; display: flex; gap: 10px;">
                    <button class="btn-primary" onclick="abrirChatRAG(${doc.id_doc})" style="flex: 1;">
                        🤖 Abrir Chat RAG
                    </button>
                    <button class="btn-primary" onclick="fecharModal()" style="flex: 1; background: var(--secondary);">
                        ✖️ Fechar
                    </button>
                </div>
            </div>
        `;
        
    } catch (error) {
        console.error('Erro ao carregar documento:', error);
        modalBody.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--primary);">
                <h3>❌ Erro ao carregar documento</h3>
                <p>${error.message}</p>
                <button class="btn-primary" onclick="fecharModal()" style="margin-top: 20px;">Fechar</button>
            </div>
        `;
    }
}

function fecharModal() {
    const modal = document.getElementById('documentModal');
    modal.classList.remove('active');
}

// Fecha modal ao clicar fora
window.addEventListener('click', (event) => {
    const modal = document.getElementById('documentModal');
    if (event.target === modal) {
        fecharModal();
    }
});

// ========================================
// ENTER NA BUSCA
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                buscarDocumentos();
            }
        });
    }
});