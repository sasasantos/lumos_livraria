from app import app, db
from models import Usuario, Cliente, Livro, Categoria, Idioma
from werkzeug.security import generate_password_hash

with app.app_context():
    # Limpar dados antigos para evitar duplicatas no teste
    db.drop_all()
    db.create_all()

    # Criar Usuário Admin
    admin = Usuario(nome='Administrador', email='admin@lumos.com', senha=generate_password_hash('admin123'))
    db.session.add(admin)

    # Criar Idiomas
    pt = Idioma(nome='Português')
    en = Idioma(nome='Inglês')
    db.session.add_all([pt, en])
    db.session.commit()

    # Criar Categorias
    cat_classicos = Categoria(nome='Clássicos')
    cat_fantasia = Categoria(nome='Fantasia')
    cat_ficcao = Categoria(nome='Ficção Científica')
    cat_romance = Categoria(nome='Romance')
    db.session.add_all([cat_classicos, cat_fantasia, cat_ficcao, cat_romance])
    db.session.commit()

    # Criar Clientes
    clientes = [
        Cliente(nome='Ana Silva', email='ana@email.com'),
        Cliente(nome='Carlos Oliveira', email='carlos@email.com'),
        Cliente(nome='Mariana Costa', email='mariana@email.com'),
        Cliente(nome='João Pereira', email='joao@email.com'),
        Cliente(nome='Fernanda Lima', email='fernanda@email.com')
    ]
    db.session.add_all(clientes)

    # Criar Livros
    livros = [
        Livro(titulo='Dom Casmurro', preco=39.90, categoria_id=cat_classicos.id, idioma_id=pt.id),
        Livro(titulo='1984', preco=52.90, categoria_id=cat_ficcao.id, idioma_id=pt.id),
        Livro(titulo='O Senhor dos Anéis', preco=119.90, categoria_id=cat_fantasia.id, idioma_id=pt.id),
        Livro(titulo='Orgulho e Preconceito', preco=47.90, categoria_id=cat_romance.id, idioma_id=pt.id),
        Livro(titulo='O Hobbit', preco=54.90, categoria_id=cat_fantasia.id, idioma_id=pt.id),
        Livro(titulo='Duna', preco=79.90, categoria_id=cat_ficcao.id, idioma_id=pt.id),
        Livro(titulo='Memórias Póstumas', preco=42.90, categoria_id=cat_classicos.id, idioma_id=pt.id),
        Livro(titulo='Harry Potter', preco=59.90, categoria_id=cat_fantasia.id, idioma_id=pt.id)
    ]
    db.session.add_all(livros)
    
    db.session.commit()
    print("Banco de dados populado com sucesso!")
