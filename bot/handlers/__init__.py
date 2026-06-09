"""Сбор всех роутеров в один список для регистрации в Dispatcher."""
from bot.handlers import start, game

routers = [start.router, game.router]
