import sys
import os
import time
import asyncio
import random
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from src.logger import get_logger
from src.playwrigth_fetch import EciScraper
# from src.telegram.bot import main_telegram_bot

load_dotenv()

logger = get_logger("ArgoTool")

required_vars = [
    "TELEGRAM_TOKEN",
    "ADMIN_CHAT_ID"
]

missing_vars = [var for var in required_vars if not os.getenv(var)]

if missing_vars:
    logger.critical(
        "Faltan variables de entorno: %s", ', '.join(missing_vars))
    sys.exit(1)

logger.info("*** Iniciando ArgoTool ***")

# main_telegram_bot()
base_url = "https://www.elcorteingles.es/apple/electronica/reacondicionados/type_description::Telefonia%20m%C3%B3vil/"

async def procesar_pagina(scraper, numero_pagina, sem):
    """Procesa una página individualmente usando el scraper compartido."""
    url = f"{base_url}{numero_pagina}/" if numero_pagina > 1 else base_url
    
    async with sem: # Controlamos cuántas pestañas se abren a la vez
        logger.info("--- Iniciando Página %d ---", numero_pagina)
        start_time = time.time()
        try:
            html_content = await scraper.fetch_page(url=url)
        except Exception as e:
            logger.warning("Error cargando página %d: %s", numero_pagina, e)
            return None
        
        elapsed_time = time.time() - start_time
        
        if not html_content:
            return None
            
        logger.info("Página %d obtenida en %.2fs", numero_pagina, elapsed_time)
        soup = BeautifulSoup(html_content, 'html.parser')
        items = soup.select('.products_list-item, .product_list-item, .grid-item')
        
        productos_encontrados = []
        for item in items:
            try:
                link_tag = item.select_one('.product_preview-title, .js-product-link')
                price_tag = item.select_one('.price-sale, .price, .product-price')

                if link_tag:
                    name = link_tag.get('title') or link_tag.get_text(strip=True)
                    price = price_tag.get_text(strip=True) if price_tag else "Sin precio"
                    href = link_tag.get('href')
                    product_url = f"https://www.elcorteingles.es{href}" if href and href.startswith('/') else href
                    
                    article = item.select_one('article')
                    product_id = article.get('id') if article else "Desconocido"

                    productos_encontrados.append({
                        "name": name,
                        "id": product_id,
                        "price": price
                    })
            except Exception:
                continue
        return productos_encontrados

async def main():
    total_products = 0
    page_num = 1
    script_start_time = time.time()
    
    # Semáforo: Máximo 4 pestañas simultáneas para no saturar RAM ni ser detectado
    sem = asyncio.Semaphore(4)
    BATCH_SIZE = 4
    keep_going = True

    # Iniciamos el scraper UNA sola vez (un solo navegador)
    async with EciScraper() as scraper:
        while keep_going:
            tasks = []
            # Preparamos un lote de tareas
            for i in range(BATCH_SIZE):
                tasks.append(procesar_pagina(scraper, page_num + i, sem))
            
            # Ejecutamos el lote en paralelo
            resultados_lote = await asyncio.gather(*tasks)
            
            items_in_batch = 0
            for i, productos in enumerate(resultados_lote):
                actual_page = page_num + i
                
                # Si es None, hubo un error (timeout, etc), saltamos pero no detenemos todo
                if productos is None:
                    continue

                count = len(productos)
                
                # Si la lista está vacía (y no es None), es que la página existe pero no tiene productos
                if count == 0:
                    logger.info("Página %d vacía. Deteniendo paginación futura.", actual_page)
                    keep_going = False
                    break # Rompemos el bucle para ignorar páginas siguientes del lote (ej. 15, 16)

                items_in_batch += count
                total_products += count
                logger.info("Página %d: %d productos", actual_page, count)
                for p in productos:
                    logger.info("Producto: %s | ID: %s | Precio: %s", p['name'], p['id'], p['price'])

            # Si keep_going sigue siendo True pero no encontramos nada (ej. todo errores), evaluamos parar
            if keep_going and items_in_batch == 0:
                logger.info("Ningún producto válido en el lote. Finalizando.")
                keep_going = False
            elif keep_going:
                page_num += BATCH_SIZE
                await asyncio.sleep(random.uniform(1.0, 2.0))

    total_elapsed_time = time.time() - script_start_time
    logger.info("Total: %d productos en %.2fs", total_products, total_elapsed_time)
    logger.info("*** ArgoTool finalizado ***")

if __name__ == "__main__":
    asyncio.run(main())
