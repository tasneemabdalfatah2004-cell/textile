from flask import Blueprint

inventory_bp = Blueprint('main', __name__)

from app.main import routes