from dataclasses import dataclass

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, UserMixin

from ..extensions import login_manager

bp = Blueprint('auth', __name__, url_prefix='/auth')


@dataclass
class AdminUser(UserMixin):
    id: int = 1
    username: str = 'admin'


@login_manager.user_loader
def load_user(user_id: str):
    # Only one admin user (credentials come from env)
    try:
        if str(user_id) == '1':
            return AdminUser(id=1, username=current_app.config.get('ADMIN_USERNAME', 'admin'))
    except Exception:
        return None
    return None


@bp.get('/login')
def login():
    return render_template('auth/login.html')


@bp.post('/login')
def login_post():
    username = (request.form.get('username') or '').strip()
    password = request.form.get('password') or ''

    if username == current_app.config['ADMIN_USERNAME'] and password == current_app.config['ADMIN_PASSWORD']:
        user = AdminUser(id=1, username=username)
        login_user(user)
        return redirect(url_for('admin.dashboard'))

    flash('Credenciales inválidas.', 'error')
    return redirect(url_for('auth.login'))


@bp.get('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


@bp.get('/logout-to-menu')
@login_required
def logout_to_menu():
    logout_user()
    return redirect(url_for('public.menu'))
