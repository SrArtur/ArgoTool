import asyncio
import random
from playwright.async_api import async_playwright, Playwright, Browser, Page, Error
from src.logger import get_logger

logger = get_logger("playwright_fetch")

class EciScraper:
    """
    Un scraper para El Corte Inglés que gestiona el ciclo de vida de Playwright
    para realizar una única configuración inicial y reutilizar el navegador.
    """
    def __init__(self, headless=True):
        self.headless = headless
        self._playwright_cm = None
        self.playwright: Playwright = None
        self.browser: Browser = None
        self.context = None

    async def __aenter__(self):
        """Inicia Playwright, el navegador y realiza la configuración inicial."""
        logger.info("Iniciando Playwright y configurando el navegador...")
        self._playwright_cm = async_playwright()
        self.playwright = await self._playwright_cm.start()
        
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless, 
            args=[
                "--no-sandbox", 
                "--disable-gpu", 
                "--disable-http2",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--window-size=1920,1080"
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='es-ES',
            timezone_id='Europe/Madrid',
            ignore_https_errors=True,
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Sec-Ch-Ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Bloqueamos recursos a nivel de contexto para que aplique a TODAS las páginas nuevas
        await self.context.route("**/*.{png,jpg,jpeg,svg,woff,woff2}", lambda route: route.abort())

        # Usamos una página temporal para la configuración inicial (cookies)
        page = await self.context.new_page()
        await self._initial_setup(page)
        await page.close()
        
        return self

    async def _initial_setup(self, page: Page):
        """Navega a la home y acepta las cookies una sola vez."""
        try:
            logger.info("Realizando configuración inicial: Navegando a la home para establecer sesión...")
            await page.goto("https://www.elcorteingles.es/", timeout=5000, wait_until="domcontentloaded")
            
            try:
                logger.info("Buscando banner de cookies...")
                await page.wait_for_selector("#onetrust-accept-btn-handler, #accept-recommended-btn-handler", state="visible", timeout=5000)
                await page.click("#onetrust-accept-btn-handler, #accept-recommended-btn-handler")
                logger.info("Cookies aceptadas en home.")
            except Error:
                logger.warning("No se encontró el banner de cookies en la home o ya estaba aceptado.")

            await asyncio.sleep(random.uniform(1.0, 2.0))
        except Exception as e:
            logger.error(f"Fallo crítico en la configuración inicial (carga de home): {e}")
            await page.screenshot(path="playwright_error_setup.png")
            raise

    async def fetch_page(self, url: str, timeout=5000):
        """Navega a una URL específica y devuelve su contenido."""
        # Creamos una página nueva (pestaña) para esta petición específica
        page = await self.context.new_page()
        
        for attempt in range(3):
            try:
                logger.info(f"Navegando a {url}")
                await page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                
                try:
                    await page.wait_for_selector(".js-product-link, .grid-item, .products_list-item, .product_preview", timeout=timeout)
                except Error as e:
                    # Si hay timeout, verificamos si es porque la página está vacía (sin resultados)
                    if "Timeout" in str(e):
                        content = await page.content()
                        if "No hay productos" in content or "no hemos encontrado" in content.lower():
                            logger.info(f"Página sin productos detectada: {url}")
                            await page.close()
                            return content
                    raise e
                
                await page.evaluate("window.scrollBy(0, 1000)")
                await asyncio.sleep(random.uniform(1.5, 3.0))
                
                content = await page.content()
                await page.close()
                return content
            except Exception as e:
                try:
                    logger.error(f"Título de la página al fallar: {await page.title()}")
                except:
                    pass
                logger.error(f"Error en intento {attempt + 1} para {url}: {e}")
                if attempt == 2:
                    await page.screenshot(path="playwright_error.png")
                    await page.close()
                    raise
                await asyncio.sleep((2 ** attempt) + random.uniform(0, 2))
        
        await page.close()
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cierra el navegador y finaliza Playwright."""
        logger.info("Cerrando el navegador Playwright.")
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()