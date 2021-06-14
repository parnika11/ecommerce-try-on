from flask import *
import sqlite3
import hashlib
import os
from werkzeug.utils import secure_filename
from instamojo_wrapper import Instamojo
import requests
import json
from flask_cors import CORS
import numpy as np
import cv2                              # Library for image processing
from math import floor

app = Flask(__name__)
app.secret_key = 'random string'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = set(['jpeg', 'jpg', 'png', 'gif'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app)

# Home page


@app.route("/")
def root():
    loggedIn, firstName, noOfItems = getLoginDetails()
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT productId, name, price, description, image, stock FROM products')
        itemData = cur.fetchall()
        cur.execute('SELECT categoryId, name FROM categories')
        categoryData = cur.fetchall()
    itemData = parse(itemData)
    return render_template('home.html', itemData=itemData, loggedIn=loggedIn, firstName=firstName, noOfItems=noOfItems, categoryData=categoryData)

# Fetch user details if logged in


def getLoginDetails():
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        if 'email' not in session:
            loggedIn = False
            firstName = ''
            noOfItems = 0
        else:
            loggedIn = True
            cur.execute(
                "SELECT userId, firstName FROM users WHERE email = '" + session['email'] + "'")
            userId, firstName = cur.fetchone()
            cur.execute(
                "SELECT count(productId) FROM kart WHERE userId = " + str(userId))
            noOfItems = cur.fetchone()[0]
    conn.close()
    return (loggedIn, firstName, noOfItems)

# Add item to cart


@app.route("/addItem", methods=["GET", "POST"])
def addItem():
    if request.method == "POST":
        name = request.form['name']
        price = float(request.form['price'])
        description = request.form['description']
        stock = int(request.form['stock'])
        categoryId = int(request.form['category'])

        # Upload image
        image = request.files['image']
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        imagename = filename
        with sqlite3.connect('database.db') as conn:
            try:
                cur = conn.cursor()
                cur.execute('''INSERT INTO products (name, price, description, image, stock, categoryId) VALUES (?, ?, ?, ?, ?, ?)''',
                            (name, price, description, imagename, stock, categoryId))
                conn.commit()
                msg = "Added successfully"
            except:
                msg = "Error occured"
                conn.rollback()
        conn.close()
        print(msg)
        return redirect(url_for('root'))

# Remove item from cart


@app.route("/removeItem")
def removeItem():
    productId = request.args.get('productId')
    with sqlite3.connect('database.db') as conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM products WHERE productID = ' + productId)
            conn.commit()
            msg = "Deleted successsfully"
        except:
            conn.rollback()
            msg = "Error occured"
    conn.close()
    print(msg)
    return redirect(url_for('root'))

# Display all items of a category


@app.route("/displayCategory")
def displayCategory():
    loggedIn, firstName, noOfItems = getLoginDetails()
    categoryId = request.args.get("categoryId")
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT products.productId, products.name, products.price, products.image, categories.name FROM products, categories WHERE products.categoryId = categories.categoryId AND categories.categoryId = " + categoryId)
        data = cur.fetchall()
    conn.close()
    categoryName = data[0][4]
    data = parse(data)
    return render_template('displayCategory.html', data=data, loggedIn=loggedIn, firstName=firstName, noOfItems=noOfItems, categoryName=categoryName)


@app.route("/account/profile")
def profileHome():
    if 'email' not in session:
        return redirect(url_for('root'))
    loggedIn, firstName, noOfItems = getLoginDetails()
    return render_template("profileHome.html", loggedIn=loggedIn, firstName=firstName, noOfItems=noOfItems)


@app.route("/account/profile/edit")
def editProfile():
    if 'email' not in session:
        return redirect(url_for('root'))
    loggedIn, firstName, noOfItems = getLoginDetails()
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT userId, email, firstName, lastName, address1, address2, zipcode, city, state, country, phone FROM users WHERE email = '" + session['email'] + "'")
        profileData = cur.fetchone()
    conn.close()
    return render_template("editProfile.html", profileData=profileData, loggedIn=loggedIn, firstName=firstName, noOfItems=noOfItems)


@app.route("/account/profile/changePassword", methods=["GET", "POST"])
def changePassword():
    if 'email' not in session:
        return redirect(url_for('loginForm'))
    if request.method == "POST":
        oldPassword = request.form['oldpassword']
        oldPassword = hashlib.md5(oldPassword.encode()).hexdigest()
        newPassword = request.form['newpassword']
        newPassword = hashlib.md5(newPassword.encode()).hexdigest()
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT userId, password FROM users WHERE email = '" + session['email'] + "'")
            userId, password = cur.fetchone()
            if (password == oldPassword):
                try:
                    cur.execute(
                        "UPDATE users SET password = ? WHERE userId = ?", (newPassword, userId))
                    conn.commit()
                    msg = "Changed successfully"
                except:
                    conn.rollback()
                    msg = "Failed"
                return render_template("changePassword.html", msg=msg)
            else:
                msg = "Wrong password"
        conn.close()
        return render_template("changePassword.html", msg=msg)
    else:
        return render_template("changePassword.html")


@app.route("/updateProfile", methods=["GET", "POST"])
def updateProfile():
    if request.method == 'POST':
        email = request.form['email']
        firstName = request.form['firstName']
        lastName = request.form['lastName']
        address1 = request.form['address1']
        zipcode = request.form['zipcode']
        city = request.form['city']
        state = request.form['state']
        country = request.form['country']
        phone = request.form['phone']
        with sqlite3.connect('database.db') as con:
            try:
                cur = con.cursor()
                cur.execute('UPDATE users SET firstName = ?, lastName = ?, address1 = ?, zipcode = ?, city = ?, state = ?, country = ?, phone = ? WHERE email = ?',
                            (firstName, lastName, address1, zipcode, city, state, country, phone, email))

                con.commit()
                msg = "Saved Successfully"
            except:
                con.rollback()
                msg = "Error occured"
        con.close()
        return redirect(url_for('editProfile'))


@app.route("/loginForm")
def loginForm():
    if 'email' in session:
        return redirect(url_for('root'))
    else:
        return render_template('login.html', error='')


@app.route("/login", methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if is_valid(email, password):
            session['email'] = email
            return redirect(url_for('root'))
        else:
            error = 'Invalid UserId / Password'
            return render_template('login.html', error=error)


@app.route("/productDescription")
def productDescription():
    loggedIn, firstName, noOfItems = getLoginDetails()
    productId = request.args.get('productId')
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT productId, name, price, description, image, stock FROM products WHERE productId = ' + productId)
        productData = cur.fetchone()
    conn.close()
    return render_template("productDescription.html", data=productData, loggedIn=loggedIn, firstName=firstName, noOfItems=noOfItems)


@app.route("/addToCart")
def addToCart():
    if 'email' not in session:
        return redirect(url_for('loginForm'))
    else:
        productId = int(request.args.get('productId'))
        with sqlite3.connect('database.db') as conn:
            cur = conn.cursor()
            cur.execute("SELECT userId FROM users WHERE email = '" +
                        session['email'] + "'")
            userId = cur.fetchone()[0]
            try:
                cur.execute(
                    "INSERT INTO kart (userId, productId) VALUES (?, ?)", (userId, productId))
                conn.commit()
                msg = "Added successfully"
            except:
                conn.rollback()
                msg = "Error occured"
        conn.close()
        return redirect(url_for('root'))


@app.route("/cart")
def cart():
    if 'email' not in session:
        return redirect(url_for('loginForm'))
    loggedIn, firstName, noOfItems = getLoginDetails()
    email = session['email']
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT userId FROM users WHERE email = '" + email + "'")
        userId = cur.fetchone()[0]
        cur.execute("SELECT products.productId, products.name, products.price, products.image FROM products, kart WHERE products.productId = kart.productId AND kart.userId = " + str(userId))
        products = cur.fetchall()
    totalPrice = 0
    for row in products:
        totalPrice += row[2]
    return render_template("cart.html", products=products, totalPrice=totalPrice, loggedIn=loggedIn, firstName=firstName, noOfItems=noOfItems)


@app.route("/checkout")
def checkout():
    if 'email' not in session:
        return redirect(url_for('loginForm'))
    loggedIn, firstName, noOfItems = getLoginDetails()
    email = session['email']
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT userId FROM users WHERE email = '" + email + "'")
        userId = cur.fetchone()[0]
        cur.execute("SELECT products.productId, products.name, products.price, products.image FROM products, kart WHERE products.productId = kart.productId AND kart.userId = " + str(userId))
        products = cur.fetchall()
    totalPrice = 0
    for row in products:
        totalPrice += row[2]
    return render_template("checkout.html", products=products, totalPrice=totalPrice, loggedIn=loggedIn, firstName=firstName, noOfItems=noOfItems)


@app.route("/instamojo")
def instamojo():
    return render_template("instamojo.html")


@app.route("/removeFromCart")
def removeFromCart():
    if 'email' not in session:
        return redirect(url_for('loginForm'))
    email = session['email']
    productId = int(request.args.get('productId'))
    with sqlite3.connect('database.db') as conn:
        cur = conn.cursor()
        cur.execute("SELECT userId FROM users WHERE email = '" + email + "'")
        userId = cur.fetchone()[0]
        try:
            cur.execute("DELETE FROM kart WHERE userId = " +
                        str(userId) + " AND productId = " + str(productId))
            conn.commit()
            msg = "removed successfully"
        except:
            conn.rollback()
            msg = "error occured"
    conn.close()
    return redirect(url_for('root'))


@app.route("/logout")
def logout():
    session.pop('email', None)
    return redirect(url_for('root'))


def is_valid(email, password):
    con = sqlite3.connect('database.db')
    cur = con.cursor()
    cur.execute('SELECT email, password FROM users')
    data = cur.fetchall()
    for row in data:
        if row[0] == email and row[1] == hashlib.md5(password.encode()).hexdigest():
            return True
    return False


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Parse form data
        password = request.form['password']
        email = request.form['email']
        firstName = request.form['firstName']
        lastName = request.form['lastName']
        address1 = request.form['address1']
        zipcode = request.form['zipcode']
        city = request.form['city']
        state = request.form['state']
        country = request.form['country']
        phone = request.form['phone']

        with sqlite3.connect('database.db') as con:
            try:
                cur = con.cursor()
                cur.execute('INSERT INTO users (password, email, firstName, lastName, address1, zipcode, city, state, country, phone) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (hashlib.md5(
                    password.encode()).hexdigest(), email, firstName, lastName, address1, zipcode, city, state, country, phone))

                con.commit()

                msg = "Registered Successfully"
            except:
                con.rollback()
                msg = "Error occured"
        con.close()
        return render_template("login.html", error=msg)


@app.route("/registerationForm")
def registrationForm():
    return render_template("register.html")


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS


def parse(data):
    ans = []
    i = 0
    while i < len(data):
        curr = []
        for j in range(7):
            if i >= len(data):
                break
            curr.append(data[i])
            i += 1
        ans.append(curr)
    return ans


@app.route('/shirt.html')
def plot():
    return render_template('shirt.html')


@app.route('/predict', methods=['GET', 'POST'])
def predict():
    shirtno = int(request.form["shirt"])

    cv2.cv2.waitKey(1)
    cap = cv2.cv2.VideoCapture(0)
    ih = shirtno
    while True:
        imgarr = ["shirt6.png", 'shirt2.png', 'shirtt1.png', 'shirtt2.png', 'shirtt3.png',
                  'shirtt4.png', 'shirt5.png', 'shirtt6.png', 'shirtt7.png', 'shirtt8.png']

        #ih=input("Enter the shirt number you want to try")
        imgshirt = cv2.cv2.imread(imgarr[ih-1], 1)  # original img in bgr
        if ih == 3:
            shirtgray = cv2.cv2.cvtColor(
                imgshirt, cv2.cv2.COLOR_BGR2GRAY)  # grayscale conversion
            # there may be some issues with image threshold...depending on the color/contrast of image
            ret, orig_masks_inv = cv2.cv2.threshold(
                shirtgray, 200, 255, cv2.cv2.THRESH_BINARY)
            orig_masks = cv2.cv2.bitwise_not(orig_masks_inv)

        else:
            shirtgray = cv2.cv2.cvtColor(
                imgshirt, cv2.cv2.COLOR_BGR2GRAY)  # grayscale conversion
            # there may be some issues with image threshold...depending on the color/contrast of image
            ret, orig_masks = cv2.cv2.threshold(
                shirtgray, 0, 255, cv2.cv2.THRESH_BINARY)
            orig_masks_inv = cv2.cv2.bitwise_not(orig_masks)
        origshirtHeight, origshirtWidth = imgshirt.shape[:2]

        face_cascade = cv2.cv2.CascadeClassifier(
            'haarcascade_frontalface_default.xml')

        ret, img = cap.read()

        height = img.shape[0]
        width = img.shape[1]
        resizewidth = int(width*3/2)
        resizeheight = int(height*3/2)
        #img = cv2.cv2.resize(img[:,:,0:3],(1000,1000), interpolation = cv2.cv2.INTER_AREA)
        cv2.cv2.namedWindow("img", cv2.cv2.WINDOW_NORMAL)
        # cv2.cv2.setWindowProperty('img',cv2.cv2.WND_PROP_FULLSCREEN,cv2.cv2.cv.CV_WINDOW_FULLSCREEN)
        cv2.cv2.resizeWindow("img", (int(width*3/2), int(height*3/2)))
        gray = cv2.cv2.cvtColor(img, cv2.cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in faces:
            cv2.cv2.rectangle(img, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.cv2.rectangle(img, (100, 200), (312, 559), (255, 255, 255), 2)

    # |||||||||||||||||||||||||||||||SHIRT||||||||||||||||||||||||||||||||||||||||

            shirtWidth = 3 * w  # approx wrt face width
            # preserving aspect ratio of original image..
            shirtHeight = shirtWidth * origshirtHeight / origshirtWidth
            # Center the shirt..just random calculations..
            x1s = x-w
            x2s = x1s+3*w
            y1s = y+h
            y2s = y1s+h*4
            # Check for clipping(whetehr x1 is coming out to be negative or not..)

            if x1s < 0:
                x1s = 0
            if x2s > img.shape[1]:
                x2s = img.shape[1]
            if y2s > img.shape[0]:
                y2s = img.shape[0]
            temp = 0
            if y1s > y2s:
                temp = y1s
                y1s = y2s
                y2s = temp
            """
            if y+h >=y1s:
                y1s = 0
                y2s=0
            """
            # Re-calculate the width and height of the shirt image(to resize the image when it wud be pasted)
            shirtWidth = int(abs(x2s - x1s))
            shirtHeight = int(abs(y2s - y1s))
            y1s = int(y1s)
            y2s = int(y2s)
            x1s = int(x1s)
            x2s = int(x2s)
            """
            if not y1s == 0 and y2s == 0:
                # Re-size the original image and the masks to the shirt sizes
                shirt = cv2.cv2.resize(imgshirt, (shirtWidth,shirtHeight), interpolation = cv2.cv2.INTER_AREA) #resize all,the masks you made,the originla image,everything
                mask = cv2.cv2.resize(orig_masks, (shirtWidth,shirtHeight), interpolation = cv2.cv2.INTER_AREA)
                masks_inv = cv2.cv2.resize(orig_masks_inv, (shirtWidth,shirtHeight), interpolation = cv2.cv2.INTER_AREA)
                # take ROI for shirt from background equal to size of shirt image
                rois = img[y1s:y2s, x1s:x2s]
                    # roi_bg contains the original image only where the shirt is not
                    # in the region that is the size of the shirt.
                num=rois
                roi_bgs = cv2.cv2.bitwise_and(rois,num,mask = masks_inv)
                # roi_fg contains the image of the shirt only where the shirt is
                roi_fgs = cv2.cv2.bitwise_and(shirt,shirt,mask = mask)
                # join the roi_bg and roi_fg
                dsts = cv2.cv2.add(roi_bgs,roi_fgs)
                img[y1s:y2s, x1s:x2s] = dsts # place the joined image, saved to dst back over the original image
            """
            # Re-size the original image and the masks to the shirt sizes
            # resize all,the masks you made,the originla image,everything
            shirt = cv2.cv2.resize(
                imgshirt, (shirtWidth, shirtHeight), interpolation=cv2.cv2.INTER_AREA)
            mask = cv2.cv2.resize(
                orig_masks, (shirtWidth, shirtHeight), interpolation=cv2.cv2.INTER_AREA)
            masks_inv = cv2.cv2.resize(
                orig_masks_inv, (shirtWidth, shirtHeight), interpolation=cv2.cv2.INTER_AREA)
            # take ROI for shirt from background equal to size of shirt image
            rois = img[y1s:y2s, x1s:x2s]
            # roi_bg contains the original image only where the shirt is not
            # in the region that is the size of the shirt.
            num = rois
            roi_bgs = cv2.cv2.bitwise_and(rois, num, mask=masks_inv)
            # roi_fg contains the image of the shirt only where the shirt is
            roi_fgs = cv2.cv2.bitwise_and(shirt, shirt, mask=mask)
            # join the roi_bg and roi_fg
            dsts = cv2.cv2.add(roi_bgs, roi_fgs)
            # place the joined image, saved to dst back over the original image
            img[y1s:y2s, x1s:x2s] = dsts
            # print "blurring"

            break
        cv2.cv2.imshow("img", img)
        # cv2.cv2.setMouseCallback('img',change_dress)
        if cv2.cv2.waitKey(100) == ord('q'):
            break

    cap.release()                           # Destroys the cap object
    # Destroys all the windows created by imshow
    cv2.cv2.destroyAllWindows()

    return render_template('home.html')


if __name__ == '__main__':
    app.run(debug=True)
