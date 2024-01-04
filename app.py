
from flask import Flask, request, render_template, session, redirect
import sqlite3

app = Flask(__name__)
app.secret_key = 'secret'


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class DbReader:
    def __enter__(self):
        self.my_db = sqlite3.connect('identifier.sqlite')
        self.my_db.row_factory = dict_factory
        self.my_cursor = self.my_db.cursor()
        return self.my_cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.my_db.commit()
        self.my_db.close()


def read_database(table_name: str, selectors: dict = None):
    with DbReader() as my_cursor:
        cursor_string = f'SELECT * FROM {table_name}'
        if selectors:
            cursor_string += " WHERE "
            conditions = []
            vals = []
            for key, val in selectors.items():
                conditions.append(f'{key} = ?')
                vals.append(val)
            cursor_string += " AND ".join(conditions)
            my_cursor.execute(cursor_string, vals)
        else:
            my_cursor.execute(cursor_string)
        return my_cursor.fetchall()


def read_multiple_tables(table_names: list, conditions, where=None):
    with DbReader() as my_cursor:
        cursor_string = f'SELECT * FROM {table_names[0]}'
        for one_table in table_names[1:]:
            cursor_string += f' JOIN {one_table} ON '
            cursor_string += ' AND '.join(conditions[table_names.index(one_table) - 1])
        if where:
            cursor_string += ' WHERE '
            conditions = []
            vals = []
            for key, val in where.items():
                conditions.append(f'{key} = ?')
                vals.append(val)
            cursor_string += 'AND '.join(conditions)
            my_cursor.execute(cursor_string, vals)
        else:
            my_cursor.execute(cursor_string)
        return my_cursor.fetchall()


def write_database(table_name: str, data: dict):
    with DbReader() as my_cursor:
        cursor_string = f'INSERT INTO {table_name} ({", ".join(data.keys())}) VALUES ({", ".join(["?"] * len(data))})'
        my_cursor.execute(cursor_string, list(data.values()))


def update_database(table_name: str, data, condition):
    with DbReader() as my_cursor:
        update_expression = ", ".join([str(key) + " = '" + str(val) + "'" for key, val in data.items()])
        cursor_string = f'UPDATE {table_name} SET {update_expression} WHERE {" and ".join([f"{key} = {val}" for key, val in condition.items()])}'
        my_cursor.execute(cursor_string)


def delete_data_from_database(table_name: str, selectors: dict):
    with DbReader() as my_cursor:
        cursor_string = f'DELETE FROM {table_name}'
        if selectors:
            cursor_string += " WHERE "
            conditions = []
            vals = []
            for key, val in selectors.items():
                conditions.append(f'{key} = ?')
                vals.append(val)
            cursor_string += " AND ".join(conditions)
            my_cursor.execute(cursor_string, vals)
        else:
            my_cursor.execute(cursor_string)
        return my_cursor.fetchall()


def current_user():
    session_user = session.get('login')
    user = None
    if session_user:
        user = read_database('users', {'login': session_user})[0]
    return user


def read_cart_with_items():
    user = current_user()
    user_cart = read_multiple_tables(['cart', 'items'], [('cart.item_id = items.id',)],
                                     {'user_login': user['login']})
    for item in user_cart:
        item['total_price'] = item['quantity'] * float(item['price'])
        item.pop('description', None)
        item.pop('price', None)
        item.pop('status', None)
        item.pop('category', None)
        item.pop('id', None)
    return user_cart


@app.route('/register', methods=['GET'])
def get_register():
    if session.get('login'):
        return redirect('/user')
    return render_template('register.html')


@app.route('/register', methods=['POST'])
def register_user():
    login = request.form['login']
    password = request.form['password']
    phone = request.form['phone_number']
    name = request.form['name']
    surname = request.form['surname']
    write_database('users',
                   {'login': login, 'password': password, 'phone_number': phone, 'name': name, 'surname': surname})
    return redirect('/login')


@app.route('/login', methods=['POST'])
def login_user():
    login = request.form['login']
    password = request.form['password']
    user = read_database('users', {'login': login, 'password': password})
    if user:
        session['login'] = user[0]['login']
        return redirect('/user')
    else:
        return render_template('login.html', error='Wrong login or password!')


@app.route('/login', methods=['GET'])
def get_login():
    if session.get('login'):
        return redirect('/user')
    return render_template('login.html')


@app.route('/user', methods=['GET'])
def get_user():
    if request.method == 'GET':
        user_login = session.get('login')
        user = read_database('users', {'login': user_login})[0]
        return render_template('user-info.html', current_user=user)


@app.route('/user', methods=['POST'])
def update_user():
    if request.method == 'POST':
        update_database('users', {'password': request.form['password'],
                                  'phone_number': request.form['phone_number'], 'name': request.form['name'],
                                  'surname': request.form['surname']}, {'login': session.get('login')})
        return redirect('/user')


@app.route('/user/update', methods=['GET'])
def get_update_user():
    user_login = session.get('login')
    user = read_database('users', {'login': user_login})[0]
    return render_template('update-user.html', current_user=user)


@app.route('/logout', methods=['GET'])
def logout():
    session.pop('login')
    return redirect('/login')


@app.route('/shop/items/<item_id>', methods=['GET'])
def item_info(item_id):
    user = current_user()
    items = read_database('items', {'id': item_id})
    return render_template('items.html', items=items, current_user=user)


@app.route('/shop/items/<item_id>/review', methods=['GET', 'POST'])
def item_review(item_id):
    user = current_user()
    user_feedback = read_database('feedbacks', {'item_id': item_id, 'user_login': user['login']})
    if not user_feedback:
        user_feedback = None
    if request.method == 'POST':
        # if not user_feedback:
        write_database('feedbacks', {'item_id': item_id, 'text': request.form['text'],
                                     'rating': request.form['rating'], 'user_login': user['login']})
        # user_feedback = True
        return redirect(f'/shop/items/{item_id}/review')
    item = read_database('items', {'id': item_id})[0]
    feedbacks = read_database('feedbacks', {'item_id': item_id})
    return render_template('item_review.html', item=item, reviews=feedbacks,
                           current_user=user, user_feedback=user_feedback)


@app.route('/shop/items/<item_id>/review/<review_id>', methods=['GET', 'POST'])
def review_info(item_id, review_id):
    user = current_user()
    if user:
        if request.method == 'POST':
            update_database('feedbacks', {'text': request.form['text'], 'rating': request.form['rating']},
                            {'item_id': item_id, 'feedback_id': review_id})
        return redirect(f'/shop/items/{item_id}/review')
    else:
        return redirect(f'/login')


@app.route('/shop/items/<item_id>/review/update', methods=['GET'])
def review_info_update(item_id):
    user = current_user()
    if user:
        item = read_database('items', {'id': item_id})[0]
        feedbacks = read_database('feedbacks', {'item_id': item_id, 'user_login': user['login']})
        if feedbacks:
            feedback = feedbacks[0]
            # return read_database('feedbacks', {'item_id': item_id, 'feedback_id': review_id})
            return render_template('update_review.html', item=item, review=feedback, add_flag=False)
        else:
            return render_template('update_review.html', item=item, add_flag=True)
    else:
        return redirect('/login')


@app.route('/shop/items', methods=['GET'])
def all_items():
    session_user = session.get('login')
    user = None
    if session_user:
        user = read_database('users', {'login': session_user})[0]
    items = read_database('items')
    return render_template('items.html', items=items, current_user=user, cart_flag=False)


@app.route('/shop/cart', methods=['GET', 'POST', 'PUT', 'DELETE'])
def cart():
    user = current_user()
    if current_user:
        if request.method == 'POST':
            item_id = request.form['itm_id']
            amount = request.form['quantity']
            item_in_cart = read_database('cart', {'item_id': item_id, 'user_login': user['login']})
            if item_in_cart:
                new_amount = int(item_in_cart[0]['quantity']) + int(amount)
                update_database('cart', {'quantity': new_amount}, {'user_login': user['login'], 'item_id': item_id})
            else:
                write_database('cart', {'user_login': user['login'], 'item_id': item_id,
                                        'quantity': amount})
        user_cart = read_cart_with_items()
        return render_template('cart.html', user_cart=user_cart, current_user=user)
    else:
        return redirect('/login')


@app.route('/shop/cart/delete', methods=['POST'])
def remove_item_from_cart():
    user = current_user()
    if current_user:
        item_id = request.form.get('itm_id')
        delete_data_from_database('cart', {'item_id': item_id, 'user_login': user['login']})
        return redirect('/shop/cart')


@app.route('/shop/cart/order', methods=['GET'])
def cart_order():
    user = current_user()
    if request.method == 'GET':
        user_cart = read_cart_with_items()
        return render_template('order-form.html', user_cart=user_cart, current_user=user)


@app.route('/shop/cart/order', methods=['POST'])
def make_order():
    user = current_user()
    if request.method == 'POST':
        user_cart = read_cart_with_items()
        user_address = request.form['address']
        total_price = sum([total_price_item['total_price'] for total_price_item in user_cart])
        orders = read_database('orders')
        if orders:
            last_order_id = orders[-1]['order_id'] + 1
        else:
            last_order_id = 1
        write_database('orders', {'order_id': last_order_id, 'user_login': user['login'],
                                  'order_total_price': str(total_price),
                                  'address': user_address, 'status': 1})
        for row in user_cart:
            delete_data_from_database('cart', {'item_id': row['item_id'], 'user_login': user['login']})
            row.pop('total_price', None)
            row.pop('name', None)
            row['order_id'] = last_order_id
            write_database('order_items', row)
        return redirect('/shop/cart')


if __name__ == '__main__':
    app.run()
