from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import sqlite3
import threading
import cgi
import uuid
import os

class DatabaseManager:
    def __init__(self, database_path):
        self.database_path = database_path

    def create_tables(self):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_ids TEXT,
                FOREIGN KEY (category_ids) REFERENCES categories(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                price REAL,
                quantity INTEGER,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                image_path TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')
        conn.commit()
        conn.close()

    def execute_query(self, query, values=None):
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        if values:
            cursor.execute(query, values)
        else:
            cursor.execute(query)
        conn.commit()
        return cursor 


class CategoryHandler(BaseHTTPRequestHandler):
    db_manager = DatabaseManager('Shop.sqlite3')
    db_manager.create_tables()
    
    def _send_response(self, status_code, response_body):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))
        
    

    def do_GET(self):
        if self.path == '/categories':
            categories = self.db_manager.execute_query('SELECT * FROM categories')
            response_data = [{'id': cat[0], 'name': cat[1]} for cat in categories]
            response_body = json.dumps(response_data)
            
            self._send_response(200, response_body)
        else:
            self._send_response(404, 'Not Found')

    def do_POST(self):
        if self.path == '/categories':
            content_length = int(self.headers['Content-Length'])
            category_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

            # Assuming category_data is a dictionary with a 'name' key
            query = 'INSERT INTO categories (name) VALUES (?)'
            values = (category_data.get('name'),)
            
            # Execute the query and get the assigned ID
            cursor = self.db_manager.execute_query(query, values)
            new_category_id = cursor.lastrowid
            
            # Fetch the newly added category using its ID
            new_category = self.db_manager.execute_query('SELECT * FROM categories WHERE id = ?', (new_category_id,))
            
            # Since it's a single row, you can directly access the first element
            response_body = json.dumps(new_category.fetchone())
            self._send_response(201, response_body)
        else:
            self._send_response(404, 'Not Found')



    def do_PUT(self):
        if self.path.startswith('/categories/'):
            category_id = int(self.path.split('/')[2])
            content_length = int(self.headers['Content-Length'])
            updated_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

            for category in self.categories:
                if category.get('id') == category_id:
                    category.update(updated_data)
                    response_body = json.dumps(category)
                    self._send_response(200, response_body)
                    return

            self._send_response(404, 'Category not found')
        else:
            self._send_response(404, 'Not Found')

    def do_DELETE(self):
        if self.path.startswith('/categories/'):
            category_id = int(self.path.split('/')[2])

            for i, category in enumerate(self.categories):
                if category.get('id') == category_id:
                    deleted_category = self.categories.pop(i)
                    response_body = json.dumps(deleted_category)
                    self._send_response(200, response_body)
                    return

            self._send_response(404, 'Category not found')
        else:
            self._send_response(404, 'Not Found')
            

class ProductHandler(BaseHTTPRequestHandler):
    db_manager = DatabaseManager('Shop.sqlite3')

    def _send_response(self, status_code, response_body):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))

    # def do_GET(self):
    #     if self.path == '/products':
    #         # Retrieve products from the database
    #         products = self.db_manager.execute_query('SELECT * FROM products').fetchall()
    #         formatted_products = [{'id': p[0], 'name': p[1], 'category_ids': [int(cat_id) for cat_id in p[2].split(',') if cat_id]} for p in products]
    #         response_body = json.dumps(formatted_products)
    #         self._send_response(200, response_body)
    #     else:
    #         self._send_response(404, 'Not Found')
    
    def do_GET(self):
        if self.path == '/products':
        # Retrieve products and their prices from the database
            query = '''
                SELECT p.id, p.name, p.category_ids, GROUP_CONCAT(pr.price || ':' || pr.quantity, ';') AS prices
                FROM products p
                LEFT JOIN prices pr ON p.id = pr.product_id
                GROUP BY p.id
            '''
            products_with_prices = self.db_manager.execute_query(query).fetchall()

            formatted_products = []
            for p in products_with_prices:
                # Extract prices
                prices = [{'price': float(price.split(':')[0]), 'quantity': int(price.split(':')[1])} for price in (p[3].split(';') if p[3] else []) if price]

                # Retrieve images for the product
                image_query = 'SELECT image_path FROM images WHERE product_id = ?'
                image_values = (p[0],)
                images = self.db_manager.execute_query(image_query, image_values).fetchall()
                image_paths = [img[0] for img in images]

                # Create formatted product dictionary
                formatted_product = {
                    'id': p[0],
                    'name': p[1],
                    'category_ids': [int(cat_id) for cat_id in p[2].split(',') if cat_id],
                    'prices': prices,
                    'images': image_paths
                }
                formatted_products.append(formatted_product)

            response_body = json.dumps(formatted_products)
            self._send_response(200, response_body)
        else:
            self._send_response(404, 'Not Found')

            
    def _get_product_with_prices(self, product_id):
        # Retrieve the product with prices from the database
        query = '''
            SELECT p.id, p.name, p.category_ids, GROUP_CONCAT(pr.price || ':' || pr.quantity, ';') AS prices
            FROM products p
            LEFT JOIN prices pr ON p.id = pr.product_id
            WHERE p.id = ?
            GROUP BY p.id
        '''
        values = (product_id,)
        product_with_prices = self.db_manager.execute_query(query, values).fetchone()

        if product_with_prices:
            formatted_product = {
                'id': product_with_prices[0],
                'name': product_with_prices[1],
                'category_ids': [int(cat_id) for cat_id in product_with_prices[2].split(',') if cat_id],
                'prices': [{'price': float(price.split(':')[0]), 'quantity': int(price.split(':')[1])} for price in product_with_prices[3].split(';') if price]
            }
            return formatted_product
        else:
            return None

    
    def do_POST(self):
        if self.path == '/products':
            content_length = int(self.headers['Content-Length'])
            product_data = json.loads(self.rfile.read(content_length).decode('utf-8'))

            # Extract product details
            name = product_data.get('name')
            category_ids = product_data.get('category_ids')
            prices_data = product_data.get('prices', [])

            if name and category_ids:
                # Insert new product into the database
                category_ids_str = ','.join(map(str, category_ids))
                query = 'INSERT INTO products (name, category_ids) VALUES (?, ?)'
                values = (name, category_ids_str)
                cursor = self.db_manager.execute_query(query, values)

                # Retrieve the newly inserted product from the database
                new_product_id = cursor.lastrowid

                # Insert prices into the database
                self._insert_prices_for_product(new_product_id, prices_data)

                # Retrieve the product with prices from the database
                new_product = self._get_product_with_prices(new_product_id)

                response_body = json.dumps(new_product)
                self._send_response(201, response_body)
            else:
                self._send_response(400, 'Name and category_id are required')
        else:
            self._send_response(404, 'Not Found')

    def _insert_prices_for_product(self, product_id, prices_data):
        # Insert prices into the database for a given product
        query = 'INSERT INTO prices (product_id, price, quantity) VALUES (?, ?, ?)'
    
        for price_data in prices_data:
            values = (product_id, price_data.get('price'), price_data.get('quantity', 100))
            print(values)  # Debugging statement
            self.db_manager.execute_query(query, values)


class ImageHandler(BaseHTTPRequestHandler):
    db_manager = DatabaseManager('Shop.sqlite3')
    db_manager.create_tables()

    def _send_response(self, status_code, response_body):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(response_body.encode('utf-8'))
        
    def do_GET(self):
        if self.path =='/images':
            images = self.db_manager.execute_query('SELECT * FROM images')
            response_data = [{'id':img[0],'product_id': img[1],'image':img[2]} for img in images ]
            response_body = json.dumps(response_data)
            
            self._send_response(200, response_body)
        else:
            self._send_response(404, 'Not Found')
        
    def do_POST(self):
        if self.path == '/images':
            content_type, _ = cgi.parse_header(self.headers['Content-Type'])

            # Check if the request is sending 'multipart/form-data'
            if content_type == 'multipart/form-data':
                form_data = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST',
                             'CONTENT_TYPE': self.headers['Content-Type']}
                )

                # Extract image and product_id from the form data
                image_file = form_data['image'].file
                product_id = form_data.getvalue('product_id')

                # Save the image to a file
                image_path = self._save_image(image_file)

                # Insert image information into the database
                query = 'INSERT INTO images (product_id, image_path) VALUES (?, ?)'
                values = (product_id, image_path)
                self.db_manager.execute_query(query, values)

                self._send_response(201, 'Image uploaded successfully')
            else:
                self._send_response(400, 'Invalid Content-Type. Expected multipart/form-data')
        else:
            self._send_response(404, 'Not Found')

    def _save_image(self, image_file):
        # Specify the directory where you want to save the images
        image_directory = 'images'

        # Create the directory if it doesn't exist
        os.makedirs(image_directory, exist_ok=True)

        # Generate a unique filename for the image
        image_filename = f'image_{uuid.uuid4().hex}.png'

        # Construct the full path to save the image
        image_path = os.path.join(image_directory, image_filename)

        # Save the image to the specified path
        with open(image_path, 'wb') as f:
            f.write(image_file.read())

        return image_path
                

if __name__ == '__main__':
    host = '127.0.0.1'
    category_port = 8080
    product_port = 8081
    image_port = 8082

    # Create instances of HTTPServer
    category_server = HTTPServer((host, category_port), CategoryHandler)
    product_server = HTTPServer((host, product_port), ProductHandler)
    image_server = HTTPServer((host, image_port), ImageHandler)
    # Create threads for each server
    category_thread = threading.Thread(target=category_server.serve_forever)
    product_thread = threading.Thread(target=product_server.serve_forever)
    image_thread = threading.Thread(target=image_server.serve_forever)
    # Start both threads
    category_thread.start()
    product_thread.start()
    image_thread.start()
    
    print(f'Starting category server on http://{host}:{category_port}')
    print(f'Starting product server on http://{host}:{product_port}')
    print(f'Starting image server on http://{host}:{image_port}')
    try:
        # Join both threads to the main thread
        category_thread.join()
        product_thread.join()
        image_thread.join()
    except KeyboardInterrupt:
        category_server.shutdown()
        product_server.shutdown()
        image_server.shutdown()
        print('Servers stopped')