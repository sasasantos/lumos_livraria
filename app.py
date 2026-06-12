from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from database import db
from models import *
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, event
from sqlalchemy.engine import Engine
from flask_socketio import SocketIO, emit
import sqlite3
import os
import json
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lumos_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# =========================
# CONFIGURAÇÃO DO BANCO E UPLOADS
# =========================
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'Lumos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# Pool de conexões: reutiliza conexões abertas em vez de abrir/fechar a cada request
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'connect_args': {'check_same_thread': False}
}
app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'static', 'img')

db.init_app(app)

# =========================
# PRAGMA SQLITE: WAL + cache
# Executado uma vez na abertura de cada conexão SQLite
# =========================
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")       # write-ahead log: leituras não bloqueiam escrita
        cursor.execute("PRAGMA synchronous=NORMAL")     # menos fsync sem perder durabilidade prática
        cursor.execute("PRAGMA cache_size=-64000")      # 64 MB de cache de páginas em memória
        cursor.execute("PRAGMA temp_store=MEMORY")      # tabelas temporárias em RAM
        cursor.execute("PRAGMA mmap_size=268435456")    # memory-mapped I/O: 256 MB
        cursor.close()

# =========================
# CONFIGURAÇÃO LOGIN
# =========================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login_page'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

# =========================
# INICIALIZAÇÃO BANCO E SEEDERS
# =========================
with app.app_context():
    if not os.path.exists(os.path.join(basedir, 'instance')):
        os.makedirs(os.path.join(basedir, 'instance'))

    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    db.create_all()

    if not Usuario.query.filter_by(email='admin@lumos.com').first():
        admin = Usuario(
            nome='Administrador',
            email='admin@lumos.com',
            senha=generate_password_hash('admin123')
        )
        db.session.add(admin)
        db.session.commit()

    try:
        if not Idioma.query.first():
            db.session.add_all([
                Idioma(nome='Português'),
                Idioma(nome='Inglês'),
                Idioma(nome='Espanhol')
            ])
            db.session.commit()
    except Exception as e:
        print(f"Aviso ao popular Idiomas: {e}")

    try:
        if not Categoria.query.first():
            db.session.add_all([
                Categoria(nome='Ficção Científica'),
                Categoria(nome='Fantasia'),
                Categoria(nome='Romance'),
                Categoria(nome='Terror'),
                Categoria(nome='Desenvolvimento Pessoal')
            ])
            db.session.commit()
    except Exception as e:
        print(f"Aviso ao popular Categorias: {e}")

# =========================
# UTILITÁRIOS
# =========================
def obter_stats():
    """Calcula todos os stats do dashboard em queries eficientes."""
    total_livros = db.session.query(func.sum(Livro.estoque)).scalar() or 0
    total_clientes = db.session.query(func.count(Cliente.id)).scalar() or 0
    total_vendas_valor = db.session.query(func.sum(Venda.total)).scalar() or 0.0
    try:
        pedidos_pendentes = db.session.query(func.count(Venda.id)).filter(Venda.status == 'Pendente').scalar() or 0
    except:
        pedidos_pendentes = 0
    return total_livros, total_clientes, float(total_vendas_valor), pedidos_pendentes

def obter_dados_grafico_categorias():
    try:
        dados = db.session.query(
            Categoria.nome,
            func.sum(ItemVenda.quantidade).label('total')
        ).join(Livro, Livro.categoria_id == Categoria.id)\
         .join(ItemVenda, ItemVenda.livro_id == Livro.id)\
         .group_by(Categoria.nome).all()

        if not dados:
            return ["Sem Vendas"], [0]

        labels = [d.nome for d in dados]
        valores = [int(d.total) for d in dados]
        return labels, valores
    except Exception as e:
        print(f"Erro no gráfico por categorias: {e}")
        return ["Erro"], [0]

# =========================
# API ENDPOINTS
# =========================
@app.route('/api/stats')
@login_required
def get_stats():
    total_livros, total_clientes, total_vendas_valor, pedidos_pendentes = obter_stats()
    labels, valores = obter_dados_grafico_categorias()

    return jsonify({
        'total_livros': total_livros,
        'total_clientes': total_clientes,
        'total_vendas_valor': total_vendas_valor,
        'pedidos_pendentes': pedidos_pendentes,
        'grafico_labels': labels,
        'grafico_valores': valores
    })

# =========================
# LOGIN / LOGOUT
# =========================
@app.route('/')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    senha = request.form.get('senha')
    user = Usuario.query.filter_by(email=email).first()

    if user and check_password_hash(user.senha, senha):
        login_user(user)
        return redirect(url_for('dashboard'))

    flash('E-mail ou senha incorretos!', 'error')
    return redirect(url_for('login_page'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login_page'))

# =========================
# PÁGINAS PRINCIPAIS
# =========================
@app.route('/dashboard')
@login_required
def dashboard():
    # Uma única chamada reutilizável — sem repetição de queries
    total_livros, total_clientes, total_vendas_valor, pedidos_pendentes = obter_stats()
    labels, valores = obter_dados_grafico_categorias()

    grafico_labels_json = json.dumps(labels)
    grafico_valores_json = json.dumps(valores)

    # Apenas os 20 mais recentes, com eager load de itens em 2 queries (subquery)
    try:
        vendas_lista = Venda.query.order_by(Venda.id.desc()).limit(20).all()
    except Exception:
        vendas_lista = []

    return render_template(
        'dashboard.html',
        total_livros=total_livros,
        total_clientes=total_clientes,
        total_vendas_valor=total_vendas_valor,
        pedidos_pendentes=pedidos_pendentes,
        grafico_labels=grafico_labels_json,
        grafico_valores=grafico_valores_json,
        vendas_lista=vendas_lista
    )

@app.route('/cadastro')
@login_required
def cadastro():
    # Busca apenas o necessário para os selects — colunas leves, sem sinopse/capa
    livros = db.session.query(
        Livro.id, Livro.titulo, Livro.autor, Livro.preco,
        Livro.estoque, Livro.categoria_id, Livro.capa
    ).order_by(Livro.titulo).all()

    clientes = db.session.query(
        Cliente.id, Cliente.nome, Cliente.email, Cliente.telefone,
        Cliente.cpf, Cliente.data_nascimento, Cliente.genero_favorito, Cliente.observacoes
    ).order_by(Cliente.nome).all()

    return render_template(
        'cadastro.html',
        categorias=Categoria.query.all(),
        clientes=clientes,
        idiomas=Idioma.query.all(),
        livros=livros
    )

@app.route('/produtos')
@login_required
def produtos():
    """Página de catálogo de produtos com filtros por categoria e busca."""
    # Obter todos os livros com suas categorias
    livros = db.session.query(Livro).order_by(Livro.titulo).all()
    categorias = Categoria.query.order_by(Categoria.nome).all()
    
    return render_template(
        'produtos.html',
        livros=livros,
        categorias=categorias
    )

@app.route('/vendas')
@login_required
def vendas():
    # Vendas com limit para a listagem; livros apenas colunas essenciais
    vendas_lista = Venda.query.order_by(Venda.id.desc()).limit(100).all()

    livros = db.session.query(
        Livro.id, Livro.titulo, Livro.autor, Livro.preco,
        Livro.estoque, Livro.categoria_id, Livro.capa
    ).order_by(Livro.titulo).all()

    return render_template(
        'vendas.html',
        vendas=vendas_lista,
        clientes=Cliente.query.with_entities(Cliente.id, Cliente.nome).order_by(Cliente.nome).all(),
        livros=livros,
        categorias=Categoria.query.all()
    )

# =========================
# PÁGINAS DE EDIÇÃO
# =========================
@app.route('/editar_livro')
@login_required
def pagina_editar_livro():
    id = request.args.get('id')
    if not id:
        flash('Selecione um livro!', 'error')
        return redirect(url_for('cadastro'))

    livro = db.get_or_404(Livro, int(id))

    try: categorias = Categoria.query.all()
    except: categorias = []

    try: idiomas = Idioma.query.all()
    except: idiomas = []

    return render_template('editar_livro.html', livro=livro, categorias=categorias, idiomas=idiomas)

@app.route('/editar_cliente')
@login_required
def pagina_editar_cliente():
    id = request.args.get('id')
    if not id:
        flash('Selecione um cliente!', 'error')
        return redirect(url_for('cadastro'))

    cliente = db.get_or_404(Cliente, int(id))

    try: categorias = Categoria.query.all()
    except: categorias = []

    return render_template('editar_cliente.html', cliente=cliente, categorias=categorias)

# =========================
# CRUD CLIENTES
# =========================
@app.route('/cliente/add', methods=['POST'])
@login_required
def add_cliente():
    nome = request.form.get('nome')
    email = request.form.get('email')
    telefone = request.form.get('telefone')
    cpf = request.form.get('cpf')
    nascimento = request.form.get('nascimento')
    genero = request.form.get('genero_favorito')
    obs = request.form.get('observacoes')

    if nome and email:
        novo_cliente = Cliente(
            nome=nome, email=email, telefone=telefone, cpf=cpf,
            data_nascimento=nascimento, genero_favorito=genero, observacoes=obs
        )
        db.session.add(novo_cliente)
        db.session.commit()
        flash('Cliente cadastrado com sucesso!', 'success')

    return redirect(url_for('cadastro'))

@app.route('/cliente/delete/<int:id>')
@login_required
def delete_cliente(id):
    cliente = db.get_or_404(Cliente, id)
    db.session.delete(cliente)
    db.session.commit()
    flash('Cliente removido com sucesso!', 'success')
    return redirect(url_for('cadastro'))

@app.route('/cliente/edit/<int:id>', methods=['POST'])
@login_required
def edit_cliente(id):
    cliente = db.get_or_404(Cliente, id)
    cliente.nome = request.form.get('nome')
    cliente.email = request.form.get('email')
    cliente.telefone = request.form.get('telefone')
    cliente.cpf = request.form.get('cpf')
    cliente.data_nascimento = request.form.get('nascimento')
    cliente.genero_favorito = request.form.get('genero_favorito')
    cliente.observacoes = request.form.get('observacoes')

    db.session.commit()
    flash('Cliente atualizado com sucesso!', 'success')
    return redirect(url_for('cadastro'))

# =========================
# CRUD LIVROS
# =========================
@app.route('/livro/add', methods=['POST'])
@login_required
def add_livro():
    titulo = request.form.get('titulo')
    autor = request.form.get('autor')
    preco = request.form.get('preco')
    categoria_id = request.form.get('categoria_id')
    idioma_id = request.form.get('idioma_id')
    estoque = request.form.get('estoque')
    sinopse = request.form.get('sinopse')

    if titulo and preco:
        cat_id = int(categoria_id) if categoria_id and categoria_id.isdigit() else None
        idi_id = int(idioma_id) if idioma_id and idioma_id.isdigit() else None

        file = request.files.get('capa')
        nome_imagem = None

        if file and file.filename != '':
            nome_imagem = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], nome_imagem))

        novo_livro = Livro(
            titulo=titulo, autor=autor, preco=float(preco),
            categoria_id=cat_id, idioma_id=idi_id,
            estoque=int(estoque) if estoque else 100, sinopse=sinopse, capa=nome_imagem
        )
        db.session.add(novo_livro)
        db.session.commit()
        flash('Livro cadastrado com sucesso!', 'success')

    return redirect(url_for('cadastro'))

@app.route('/livro/delete/<int:id>')
@login_required
def delete_livro(id):
    livro = db.get_or_404(Livro, id)
    db.session.delete(livro)
    db.session.commit()
    flash('Livro removido com sucesso!', 'success')
    return redirect(url_for('cadastro'))

@app.route('/livro/edit/<int:id>', methods=['POST'])
@login_required
def edit_livro(id):
    livro = db.get_or_404(Livro, id)
    livro.titulo = request.form.get('titulo')
    livro.autor = request.form.get('autor')
    livro.preco = float(request.form.get('preco'))
    livro.estoque = int(request.form.get('estoque'))
    livro.sinopse = request.form.get('sinopse')

    categoria_id = request.form.get('categoria_id')
    idioma_id = request.form.get('idioma_id')

    livro.categoria_id = int(categoria_id) if categoria_id and categoria_id.isdigit() else None
    livro.idioma_id = int(idioma_id) if idioma_id and idioma_id.isdigit() else None

    if 'capa' in request.files:
        file = request.files['capa']
        if file and file.filename != '':
            nome_imagem = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], nome_imagem))
            livro.capa = nome_imagem

    db.session.commit()
    flash('Livro atualizado com sucesso!', 'success')
    return redirect(url_for('cadastro'))

# =========================
# CRUD VENDAS
# =========================
@app.route('/venda/add', methods=['POST'])
@login_required
def add_venda():
    nome = request.form.get('cliente_nome')
    endereco = request.form.get('endereco')
    status_pedido = request.form.get('status', 'Concluído')
    total = request.form.get('total')
    carrinho_raw = request.form.get('carrinho_json')

    if not nome:
        flash('Erro: O nome do cliente é obrigatório.', 'error')
        return redirect(url_for('vendas'))

    if not total:
        flash('Erro: O valor total da venda não foi calculado.', 'error')
        return redirect(url_for('vendas'))

    try:
        total_float = float(total)
        if total_float <= 0:
            flash('Erro: O valor total da venda deve ser maior que zero.', 'error')
            return redirect(url_for('vendas'))
    except ValueError:
        flash('Erro: O valor total enviado é inválido.', 'error')
        return redirect(url_for('vendas'))

    if not carrinho_raw or carrinho_raw.strip() in ['', '[]', '{}']:
        flash('Erro: Seu carrinho está vazio ou não foi carregado corretamente.', 'error')
        return redirect(url_for('vendas'))

    try:
        lista_produtos = json.loads(carrinho_raw)
    except Exception:
        flash('Erro: O formato dos dados estruturais do carrinho é inválido.', 'error')
        return redirect(url_for('vendas'))

    if not lista_produtos:
        flash('Erro: Nenhum produto foi detectado dentro do carrinho.', 'error')
        return redirect(url_for('vendas'))

    # Coleta todos os IDs do carrinho e busca em 1 query só
    try:
        ids_solicitados = [int(str(item['id']).strip()) for item in lista_produtos if 'id' in item]
    except (ValueError, KeyError):
        flash('Erro: Código inválido identificado no carrinho.', 'error')
        return redirect(url_for('vendas'))

    livros_mapa = {
        livro.id: livro
        for livro in Livro.query.filter(Livro.id.in_(ids_solicitados)).all()
    }

    itens_processados = []
    for item in lista_produtos:
        if 'id' not in item or 'qtd' not in item:
            flash('Erro: Existem itens mal estruturados no carrinho.', 'error')
            return redirect(url_for('vendas'))

        try:
            livro_id = int(str(item['id']).strip())
            qtd_pedida = int(item['qtd'])
        except ValueError:
            flash('Erro: Código ou quantidade inválidos identificados no carrinho.', 'error')
            return redirect(url_for('vendas'))

        livro = livros_mapa.get(livro_id)
        if not livro:
            flash(f'Erro: O livro com ID #{livro_id} não consta no catálogo do sistema.', 'error')
            return redirect(url_for('vendas'))

        if livro.estoque < qtd_pedida:
            flash(f'Erro: Estoque insuficiente para "{livro.titulo}". Disponível: {livro.estoque} un. Solicitado: {qtd_pedida} un.', 'error')
            return redirect(url_for('vendas'))

        itens_processados.append({'livro_objeto': livro, 'quantidade': qtd_pedida})

    try:
        nova_venda = Venda(
            cliente_nome=nome,
            endereco=endereco if endereco else "Retirada no Balcão",
            total=total_float,
            status=status_pedido
        )
        db.session.add(nova_venda)
        db.session.flush()

        for item in itens_processados:
            livro = item['livro_objeto']
            qtd = item['quantidade']
            livro.estoque -= qtd
            novo_item = ItemVenda(venda_id=nova_venda.id, livro_id=livro.id, quantidade=qtd)
            db.session.add(novo_item)

        db.session.commit()
        socketio.emit('atualizar_dashboard', {'mensagem': 'Nova venda realizada!'})
        flash('Venda processada e estoque atualizado com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Falha interna no Banco de Dados: {str(e)}', 'error')

    return redirect(url_for('vendas'))

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
