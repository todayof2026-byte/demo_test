"""Page Object Model: one class per logical page on automationexercise.com."""

from src.pages.base_page import BasePage
from src.pages.cart_page import CartPage
from src.pages.home_page import HomePage
from src.pages.login_page import LoginPage
from src.pages.product_page import ProductPage
from src.pages.search_results_page import SearchResultsPage

__all__ = [
    "BasePage",
    "CartPage",
    "HomePage",
    "LoginPage",
    "ProductPage",
    "SearchResultsPage",
]
