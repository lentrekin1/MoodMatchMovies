import json
import os
from dotenv import load_dotenv
from flask import Flask
from models import db, Film
import zipfile

load_dotenv()
from flask_cors import CORS
from routes import register_routes

# src/ directory and project root (one level up)
current_directory = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_directory)

# Serve React build files from <project_root>/frontend/dist
app = Flask(__name__,
    static_folder=os.path.join(project_root, 'frontend', 'dist'),
    static_url_path='')
CORS(app)

# Configure SQLite database - using 3 slashes for relative path
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database with app
db.init_app(app)

# Register routes
register_routes(app)

# Function to initialize database, change this to your own database initialization logic
def init_db():
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Initialize database with data from init.json if empty
        if Film.query.count() == 0:
            json_file_path = os.path.join(current_directory, 'data/final_movies.json')
            with open(json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                for film_data in data:
                    film = Film(
                        tconst = film_data["tconst"],
                        title = film_data["title"],
                        year = int(film_data["year"]),
                        genres = film_data["genres"],
                        runtime = int(film_data["runtime"]),
                        imdb_score = film_data["imdb_avg"],
                        imdb_num_ratings = film_data["imdb_num_ratings"],
                        tomatometer = film_data["tomatometer"],
                        plot = film_data["plot"],
                        rating = film_data["rating"],
                        director = film_data["director"],
                        actors = film_data["actors"],
                        emotions = str(film_data["emotions"]),
                        svd_embedding = str(film_data["svd_embedding"]),
                        num_lb_reviews = film_data["num_lb_reviews"],
                        num_imdb_reviews = film_data["num_imdb_reviews"],
                        num_rt_reviews = film_data["num_rt_reviews"]
                    )
                    db.session.add(film)
            
            db.session.commit()
            print("Database initialized with film data")
init_db()

# Extract posters
poster_dir = os.path.join(project_root, 'assets', 'posters')
poster_zip_path = os.path.join(project_root, 'assets', 'posters.zip')
if not os.path.isdir(poster_dir):
    if os.path.exists(poster_zip_path):
        print("Unzipping posters...")
        with zipfile.ZipFile(poster_zip_path, 'r') as zf:
            for member in zf.infolist():
                name = member.filename

                if name.endswith('/'):
                    continue

                if not name.startswith("posters/"):
                    continue

                relative_path = name[len("posters/"):]
                target_path = os.path.join(poster_dir, relative_path)

                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                with zf.open(member) as source, open(target_path, "wb") as target:
                    target.write(source.read())
        print("Posters unzipped.")
    else:
        print("posters.zip not found, skipping poster extraction.")

# Extract reviews
reviews_dir = os.path.join(project_root, 'src', 'data', 'reviews')
review_zip_path = os.path.join(project_root, 'reviews.zip')
if not os.path.isdir(reviews_dir):
    if os.path.exists(review_zip_path):
        print("Unzipping reviews...")
        with zipfile.ZipFile(review_zip_path, 'r') as zf:
            for member in zf.infolist():
                name = member.filename

                if name.endswith('/'):
                    continue

                if not name.startswith("reviews/"):
                    continue

                relative_path = name[len("reviews/"):]
                target_path = os.path.join(reviews_dir, relative_path)

                os.makedirs(os.path.dirname(target_path), exist_ok=True)

                with zf.open(member) as source, open(target_path, "wb") as target:
                    target.write(source.read())
        print("Reviews unzipped.")
    else:
        print("reviews.zip not found, skipping review extraction.")

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5001)