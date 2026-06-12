from database import db
from flask_login import UserMixin

class Categoria(db.Model):
    __tablename__ = 'categoria'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)


class Cliente(db.Model):
    __tablename__ = 'cliente'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(120))
    telefone = db.Column(db.String(20))
    cpf = db.Column(db.String(20))
    data_nascimento = db.Column(db.String(20))
    genero_favorito = db.Column(db.String(50))
    observacoes = db.Column(db.Text)

    __table_args__ = (
        db.Index('idx_cliente_nome', 'nome'),
        db.Index('idx_cliente_email', 'email'),
    )


class Idioma(db.Model):
    __tablename__ = 'idioma'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50))


class Livro(db.Model):
    __tablename__ = 'livro'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(150))
    autor = db.Column(db.String(100))
    preco = db.Column(db.Float)
    estoque = db.Column(db.Integer, default=0)
    sinopse = db.Column(db.Text)

    categoria_id = db.Column(
        db.Integer,
        db.ForeignKey('categoria.id', ondelete='SET NULL'),
        nullable=True
    )

    idioma_id = db.Column(
        db.Integer,
        db.ForeignKey('idioma.id', ondelete='SET NULL'),
        nullable=True
    )

    categoria = db.relationship(
        'Categoria',
        backref='livros',
        lazy='joined'
    )

    idioma = db.relationship(
        'Idioma',
        backref='livros',
        lazy='joined'
    )

    capa = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.Index('idx_livro_categoria', 'categoria_id'),
        db.Index('idx_livro_titulo', 'titulo'),
    )


class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuario'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    senha = db.Column(db.String(200))


class ItemVenda(db.Model):
    __tablename__ = 'item_venda'

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(
        db.Integer,
        db.ForeignKey('venda.id', ondelete='CASCADE')
    )

    livro_id = db.Column(
        db.Integer,
        db.ForeignKey('livro.id', ondelete='CASCADE')
    )

    quantidade = db.Column(db.Integer)

    livro = db.relationship(
        'Livro',
        lazy='subquery'
    )

    __table_args__ = (
        db.Index('idx_item_venda_venda_id', 'venda_id'),
        db.Index('idx_item_venda_livro_id', 'livro_id'),
    )


class Venda(db.Model):
    __tablename__ = 'venda'

    id = db.Column(db.Integer, primary_key=True)
    cliente_nome = db.Column(db.String(100))
    endereco = db.Column(db.String(200))
    total = db.Column(db.Float)
    data = db.Column(db.DateTime, server_default=db.func.now())
    status = db.Column(db.String(50), default="Concluído")

    itens = db.relationship(
        'ItemVenda',
        backref='venda',
        lazy='subquery',
        cascade='all, delete-orphan'
    )

    __table_args__ = (
        db.Index('idx_venda_status', 'status'),
        db.Index('idx_venda_data', 'data'),
    )
