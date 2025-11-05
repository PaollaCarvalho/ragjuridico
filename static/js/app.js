// ============================================================================
// CONFIGURAÇÃO DA API
// ============================================================================

const API_BASE_URL = 'http://localhost:8000';  // URL da sua API FastAPI

// ============================================================================
// FUNÇÕES DE API
// ============================================================================

/**
 * Busca documentos na API usando busca inteligente
 */
async function buscarDocumentosAPI(query, filtros = {}) {
    try {
        // Monta URL com query params
        const params = new URLSearchParams({
            q: query,
            limite: 20
        });

        // Adiciona filtros opcionais
        if (filtros.tipo) {
            params.append('tipo', filtros.tipo);
        }
        if (filtros.data_inicio) {
            params.append('data_inicio', filtros.data_inicio);
        }
        if (filtros.data_fim) {
            params.append('data_fim', filtros.data_fim);
        }

        const url = `${API_BASE_URL}/buscar?${params.toString()}`;
        
        console.log('Buscando na API:', url);
        
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`Erro HTTP: ${response.status}`);
        }
        
        const data = await response.json();
        
        console.log('Resposta da API:', data);
        
        return data;
        
    } catch (error) {
        console.error('Erro ao buscar documentos:', error);
        
        // Retorna estrutura vazia em caso de erro
        return {
            total: 0,
            documentos: [],
            tempo_busca: 0,
            erro: error.message
        };
    }
}

/**
 * Busca documento específico por ID
 */
async function buscarDocumentoPorID(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/documento/${id}`);
        
        if (!response.ok) {
            throw new Error(`Documento não encontrado: ${id}`);
        }
        
        return await response.json();
        
    } catch (error) {
        console.error('Erro ao buscar documento:', error);
        return null;
    }
}

/**
 * Busca estatísticas do banco
 */
async function buscarEstatisticas() {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        return await response.json();
    } catch (error) {
        console.error('Erro ao buscar estatísticas:', error);
        return null;
    }
}

// ============================================================================
// FUNÇÕES DE UI
// ============================================================================

/**
 * Função principal de busca (conectada ao botão)
 */
async function buscarDocumentos() {
    const searchTerm = document.getElementById('searchInput').value.trim();
    
    // Valida se digitou algo
    if (!searchTerm) {
        alert('Por favor, digite algo para buscar!');
        return;
    }
    
    // Captura filtros
    const filtros = {
        tipo: document.getElementById('filterTipo').value,
        data_inicio: document.getElementById('filterDataInicio').value,
        data_fim: document.getElementById('filterDataFim').value
    };
    
    // Mostra loading
    document.getElementById('loading').classList.add('active');
    document.getElementById('resultsSection').style.display = 'none';
    
    // Busca na API
    const resultado = await buscarDocumentosAPI(searchTerm, filtros);
    
    // Exibe resultados
    exibirResultados(resultado);
}

/**
 * Exibe resultados na tela
 */
function exibirResultados(resultado) {
    // Remove loading
    document.getElementById('loading').classList.remove('active');
    document.getElementById('resultsSection').style.display = 'block';
    
    const resultsGrid = document.getElementById('resultsGrid');
    const resultsCount = document.getElementById('resultsCount');
    const emptyState = document.getElementById('emptyState');
    
    // Atualiza contador
    const total = resultado.total || 0;
    const tempo = resultado.tempo_busca || 0;
    
    resultsCount.textContent = `${total} documento${total !== 1 ? 's' : ''} encontrado${total !== 1 ? 's' : ''} (${tempo}s)`;
    
    // Se não encontrou nada
    if (total === 0) {
        resultsGrid.style.display = 'none';
        emptyState.style.display = 'block';
        
        // Mostra mensagem de erro se houver
        if (resultado.erro) {
            emptyState.innerHTML = `
                <div class="empty-icon">⚠️</div>
                <p class="empty-text">Erro ao buscar documentos</p>
                <p style="color: var(--text-light); font-size: 0.9rem; margin-top: 10px;">
                    ${resultado.erro}
                </p>
                <p style="color: var(--text-light); font-size: 0.85rem; margin-top: 10px;">
                    Verifique se a API está rodando em ${API_BASE_URL}
                </p>
            `;
        }
        
        return;
    }
    
    // Mostra grid
    resultsGrid.style.display = 'grid';
    emptyState.style.display = 'none';
    
    // Gera cards dos documentos
    resultsGrid.innerHTML = resultado.documentos.map(doc => {
        // Pega primeiro envolvido e primeiro CPF/CNPJ
        const envolvido = doc.envolvidos[0] || { empresa: 'N/A', representante: 'N/A' };
        const cpf_cnpj = doc.cpf_cnpj[0] || { cpf: '-', cnpj: '-' };
        
        // Formata data
        const data = doc.data_assinatura 
            ? new Date(doc.data_assinatura).toLocaleDateString('pt-BR')
            : 'Data não disponível';
        
        // Calcula "progresso" baseado no score (0-100)
        const progresso = doc.score_relevancia || 0;
        
        return `
            <div class="doc-card" onclick="abrirDocumento(${doc.id_doc})">
                <div class="doc-header">
                    <div class="doc-icon">📄</div>
                    <div class="doc-header-text">
                        <span class="doc-type">${doc.tipo_doc}</span>
                        <h3 class="doc-title">${envolvido.empresa}</h3>
                        <p class="doc-date">📅 ${data}</p>
                    </div>
                </div>
                <div class="doc-info">
                    <div class="doc-info-item">
                        <strong>Representante:</strong>
                        <span>${envolvido.representante}</span>
                    </div>
                    ${cpf_cnpj.cpf ? `
                    <div class="doc-info-item">
                        <strong>CPF:</strong>
                        <span>${cpf_cnpj.cpf}</span>
                    </div>
                    ` : ''}
                    ${cpf_cnpj.cnpj ? `
                    <div class="doc-info-item">
                        <strong>CNPJ:</strong>
                        <span>${cpf_cnpj.cnpj}</span>
                    </div>
                    ` : ''}
                    ${doc.score_relevancia ? `
                    <div class="doc-info-item">
                        <strong>Relevância:</strong>
                        <span>${doc.score_relevancia.toFixed(1)}%</span>
                    </div>
                    ` : ''}
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${progresso}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Abre modal com documento
 */
async function abrirDocumento(id) {
    console.log('Abrindo documento:', id);
    
    // Busca detalhes do documento
    const doc = await buscarDocumentoPorID(id);
    
    if (!doc) {
        alert('Erro ao carregar documento!');
        return;
    }
    
    // Atualiza modal
    document.getElementById('modalTitle').textContent = doc.nome_arquivo;
    
    // TODO: Carregar PDF real aqui
    // Por enquanto, mostra mensagem
    document.getElementById('modalBody').innerHTML = `
        <div style="padding: 40px; text-align: center;">
            <h2>📄 ${doc.nome_arquivo}</h2>
            <p style="margin: 20px 0; color: var(--text-light);">
                Visualização do PDF será implementada aqui.
            </p>
            <div style="background: var(--bg-light); padding: 20px; border-radius: 8px; margin-top: 20px; text-align: left;">
                <h3>Detalhes:</h3>
                <p><strong>Tipo:</strong> ${doc.tipo_doc}</p>
                <p><strong>Data:</strong> ${doc.data_assinatura ? new Date(doc.data_assinatura).toLocaleDateString('pt-BR') : 'N/A'}</p>
                <hr style="margin: 15px 0;">
                <h3>Envolvidos:</h3>
                ${doc.envolvidos.map(e => `
                    <p><strong>${e.empresa}</strong><br>
                    Representante: ${e.representante}</p>
                `).join('')}
                <hr style="margin: 15px 0;">
                <h3>CPF/CNPJ:</h3>
                ${doc.cpf_cnpj.map(c => `
                    <p>
                        ${c.cpf ? `CPF: ${c.cpf}` : ''}
                        ${c.cpf && c.cnpj ? ' | ' : ''}
                        ${c.cnpj ? `CNPJ: ${c.cnpj}` : ''}
                    </p>
                `).join('')}
            </div>
        </div>
    `;
    
    // Abre modal
    document.getElementById('documentModal').classList.add('active');
}

/**
 * Fecha modal
 */
function fecharModal() {
    document.getElementById('documentModal').classList.remove('active');
}

// ============================================================================
// EVENT LISTENERS
// ============================================================================

// Busca ao pressionar Enter
document.getElementById('searchInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        buscarDocumentos();
    }
});

// Fecha modal ao clicar fora
document.getElementById('documentModal').addEventListener('click', function(e) {
    if (e.target === this) {
        fecharModal();
    }
});

// Carrega estatísticas ao abrir a página (opcional)
window.addEventListener('load', async function() {
    console.log('🚀 Sistema carregado!');
    console.log('📡 API configurada em:', API_BASE_URL);
    
    // Verifica se API está online
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const health = await response.json();
        console.log('✅ API Status:', health);
    } catch (error) {
        console.warn('⚠️ API não está respondendo:', error.message);
        console.warn('💡 Execute: python api.py ou uvicorn api:app --reload');
    }
    
    // Carrega estatísticas (opcional)
    const stats = await buscarEstatisticas();
    if (stats) {
        console.log('📊 Estatísticas:', stats);
    }
});

// ============================================================================
// EXPORTA FUNÇÕES (para uso global)
// ============================================================================

// As funções já estão disponíveis globalmente via onclick no HTML
// Mas você pode adicionar mais funcionalidades aqui

console.log('✅ Script carregado com sucesso!');

// ============================================================================
// RAG - CHAT INTERFACE
// ============================================================================

let documentoAtualRAG = null;
let chatHistory = [];

async function abrirDocumento(id) {
    const doc = await buscarDocumentoPorID(id);
    documentoAtualRAG = doc;
    
    document.getElementById('modalTitle').textContent = doc.nome_arquivo;
    
    document.getElementById('modalBody').innerHTML = `
        <div style="display: flex; height: 100%; gap: 20px;">
            <!-- Coluna Esquerda: Info + PDF -->
            <div style="flex: 1; display: flex; flex-direction: column;">
                <div style="background: var(--bg-light); padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                    <p><strong>Tipo:</strong> ${doc.tipo_doc}</p>
                    <p><strong>Data:</strong> ${doc.data_assinatura || 'N/A'}</p>
                    <p><strong>Empresa:</strong> ${doc.envolvidos[0]?.empresa || 'N/A'}</p>
                </div>
                
                <div style="flex: 1; background: #fafafa; border-radius: 8px; padding: 20px; text-align: center;">
                    <p style="color: var(--text-light);">📄 Visualização do PDF será implementada aqui</p>
                </div>
            </div>
            
            <!-- Coluna Direita: Chat RAG -->
            <div style="width: 450px; display: flex; flex-direction: column; border-left: 2px solid var(--border); padding-left: 20px;">
                <div style="margin-bottom: 15px;">
                    <h3 style="margin: 0 0 10px 0;">💬 Assistente Inteligente</h3>
                    <button 
                        id="btnIniciarRAG" 
                        class="btn-primary" 
                        onclick="iniciarRAG(${doc.id_doc})"
                        style="width: 100%; padding: 12px;">
                        🤖 Iniciar Conversa
                    </button>
                </div>
                
                <div id="ragStatus" style="display: none; padding: 10px; background: var(--focus-bg); border-radius: 6px; margin-bottom: 15px; text-align: center;">
                    <span id="statusText">Processando documento...</span>
                </div>
                
                <div id="chatContainer" style="display: none; flex: 1; display: flex; flex-direction: column;">
                    <!-- Área de mensagens -->
                    <div id="chatMessages" style="flex: 1; overflow-y: auto; padding: 15px; background: var(--bg-light); border-radius: 8px; margin-bottom: 15px;">
                        <p style="text-align: center; color: var(--text-light);">
                            Faça uma pergunta sobre este documento 👇
                        </p>
                    </div>
                    
                    <!-- Input de pergunta -->
                    <div style="display: flex; gap: 10px;">
                        <textarea 
                            id="perguntaRAG" 
                            placeholder="Ex: Qual o valor do contrato?"
                            style="flex: 1; padding: 12px; border: 2px solid var(--border); border-radius: 6px; resize: none; height: 60px;"
                            onkeypress="if(event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); enviarPerguntaRAG(); }"
                        ></textarea>
                        <button 
                            onclick="enviarPerguntaRAG()" 
                            class="btn-primary"
                            style="padding: 0 20px;">
                            Enviar
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('documentModal').classList.add('active');
    chatHistory = [];
}

async function iniciarRAG(id_doc) {
    const btn = document.getElementById('btnIniciarRAG');
    const status = document.getElementById('ragStatus');
    const chat = document.getElementById('chatContainer');
    
    // Desabilita botão e mostra loading
    btn.disabled = true;
    btn.textContent = '⏳ Processando...';
    status.style.display = 'block';
    
    try {
        // Processa documento no backend
        const response = await fetch(`${API_BASE_URL}/rag/processar/${id_doc}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.status === 'processado' || data.status === 'ja_processado') {
            // Sucesso! Mostra chat
            status.innerHTML = `<span style="color: green;">✅ Documento pronto para perguntas!</span>`;
            
            setTimeout(() => {
                status.style.display = 'none';
                btn.style.display = 'none';
                chat.style.display = 'flex';
            }, 1500);
            
        } else {
            throw new Error('Erro ao processar documento');
        }
        
    } catch (error) {
        console.error('Erro ao iniciar RAG:', error);
        status.innerHTML = `<span style="color: red;">❌ Erro ao processar documento</span>`;
        btn.disabled = false;
        btn.textContent = '🔄 Tentar Novamente';
    }
}

async function enviarPerguntaRAG() {
    const pergunta = document.getElementById('perguntaRAG').value.trim();
    
    if (!pergunta) return;
    
    const chatMessages = document.getElementById('chatMessages');
    
    // Adiciona pergunta do usuário
    adicionarMensagem('user', pergunta);
    
    // Limpa input
    document.getElementById('perguntaRAG').value = '';
    
    // Mostra loading
    adicionarMensagem('bot', '💭 Pensando...');
    
    try {
        // Chama API RAG
        const response = await fetch(`${API_BASE_URL}/rag/perguntar`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                id_doc: documentoAtualRAG.id_doc,
                pergunta: pergunta
            })
        });
        
        const data = await response.json();
        
        // Remove loading
        removerUltimaMensagem();
        
        // Adiciona resposta
        adicionarMensagem('bot', data.resposta);
        
        // Salva no histórico
        chatHistory.push({pergunta, resposta: data.resposta});
        
    } catch (error) {
        console.error('Erro ao perguntar:', error);
        removerUltimaMensagem();
        adicionarMensagem('bot', '❌ Erro ao gerar resposta. Tente novamente.');
    }
}

function adicionarMensagem(tipo, texto) {
    const chatMessages = document.getElementById('chatMessages');
    
    const msgDiv = document.createElement('div');
    msgDiv.style.cssText = `
        margin-bottom: 15px;
        padding: 12px;
        border-radius: 8px;
        ${tipo === 'user' 
            ? 'background: var(--primary); color: white; margin-left: 40px; text-align: right;' 
            : 'background: white; margin-right: 40px; border: 1px solid var(--border);'}
    `;
    
    msgDiv.innerHTML = `
        <strong>${tipo === 'user' ? '👤 Você' : '🤖 Assistente'}</strong>
        <p style="margin: 8px 0 0 0; line-height: 1.5;">${texto}</p>
    `;
    
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removerUltimaMensagem() {
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages.lastChild) {
        chatMessages.removeChild(chatMessages.lastChild);
    }
}