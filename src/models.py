from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Film(db.Model):
    __tablename__ = 'films'
    tconst = db.Column(db.String(64), primary_key=True)
    title = db.Column(db.String(64), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    genres = db.Column(db.String(1024))
    runtime = db.Column(db.Integer, nullable=False)
    imdb_score = db.Column(db.Float, nullable=False)
    imdb_num_ratings = db.Column(db.Integer, nullable=False)
    tomatometer = db.Column(db.Integer, nullable=True)
    plot = db.Column(db.String(1024))
    director = db.Column(db.String(128))
    actors = db.Column(db.String(1024))
    rating = db.Column(db.String(8))
    emotions = db.Column(db.String(1024))
    svd_embedding = db.Column(db.String(4096))
    num_lb_reviews = db.Column(db.Integer)
    num_imdb_reviews = db.Column(db.Integer)
    num_rt_reviews = db.Column(db.Integer)
    
    def __repr__(self):
        return f'Film {self.tconst}: {self.title}'