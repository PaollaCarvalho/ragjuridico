

// ========================================
// BANCO DE DADOS SIMULADO DE USUÁRIOS
// ========================================
const usuarios = [
    { 
        email: 'paola.carvalho@alunos.bpkedu.com', 
        senha: '1234', 
        nome: 'Administrador',
        tipo: 'admin'
    },
    { 
        email: 'usuario@biopark.com.br', 
        senha: 'senha123', 
        nome: 'Usuário Teste',
        tipo: 'user'
    }
    // Adicione mais usuários aqui conforme necessário
];

// ========================================
// FUNÇÃO DE LOGIN
// ========================================
document.getElementById('loginForm').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const email = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const lembrarMe = document.getElementById('remember').checked;
    
    // Validação básica
    if (!email || !password) {
        alert('Por favor, preencha todos os campos!');
        return;
    }
    
    // Busca usuário no banco de dados simulado
    const usuarioEncontrado = usuarios.find(u => 
        u.email.toLowerCase() === email.toLowerCase() && 
        u.senha === password
    );
    
    if (usuarioEncontrado) {
        // Prepara dados do usuário para salvar
        const dadosUsuario = {
            email: usuarioEncontrado.email,
            nome: usuarioEncontrado.nome,
            tipo: usuarioEncontrado.tipo,
            dataLogin: new Date().toISOString()
        };
        
        // Salva no localStorage
        localStorage.setItem('usuarioLogado', JSON.stringify(dadosUsuario));
        
        // Se marcou "Lembrar-me", salva também
        if (lembrarMe) {
            localStorage.setItem('lembrarEmail', email);
        } else {
            localStorage.removeItem('lembrarEmail');
        }
        
        // Redireciona para o sistema
        alert('✅ Login realizado com sucesso!\n\nBem-vindo(a), ' + usuarioEncontrado.nome + '!');
        window.location.href = 'index.html'; 
        
    } else {
        // Login falhou
        alert(' Email ou senha incorretos!');
        document.getElementById('password').value = ''; 
        document.getElementById('password').focus();
    }
});