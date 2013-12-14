# -*- coding: utf-8 -*-
"""
    SmithyForge
    ~~~~~~~~

    Smithy's Anvil reloaded.

    :copyright: (c) 2010 by x0l
    :license: BSD, see LICENSE for more details.
"""

from flask import Flask, request, session, url_for, redirect, \
                    render_template, abort, g, flash

from flask.ext.sqlalchemy import SQLAlchemy

from werkzeug import check_password_hash, generate_password_hash

import bs4
import requests
import datetime

app = Flask(__name__)


# CONFIGURATION

# app.config['DEBUG']                   = True
# app.config['PER_PAGE']                = 30
app.config['SECRET_KEY']              = '\xd86\x0e\xaaGCR\xce\x025?\x99\xc7\xce\xe9f\xee\x0b\xfc5\x96\xe6o\x1b'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://xav@localhost:5432/smithytest'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://vwiikxygjdqulb:0V890bb0Xt3Bv9gwid6hQ7q0wg@ec2-54-247-64-118.eu-west-1.compute.amazonaws.com:5432/dfvrpso9di800p'
db = SQLAlchemy(app)


# DATABASE DEFINITIONS

class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    email    = db.Column(db.String(120), unique=True)
    pw_hash  = db.Column(db.String(80))
    cdlcs    = db.relationship('CDLC', backref='User', lazy='dynamic')

    def __init__(self, username, email, password):
        self.username = username
        self.email    = email
        self.pw_hash  = generate_password_hash(password)

    def __repr__(self):
        return '<User %r>' % self.username


class CDLC(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(80))
    artist      = db.Column(db.String(80))
    album       = db.Column(db.String(80))
    year        = db.Column(db.Integer)
    tags        = db.Column(db.String(200))
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'))
    last_update = db.Column(db.DateTime)
    reviews     = db.relationship('Review', backref='CDLC', lazy='dynamic')
    url_pc      = db.Column(db.String(120))
    url_mac     = db.Column(db.String(120))
    url_xbox    = db.Column(db.String(120))
    url_ps3     = db.Column(db.String(120))
    artwork     = db.Column(db.String(120))
    dl_count    = db.Column(db.Integer)
    tr_guitar   = db.Column(db.Boolean)
    tr_bass     = db.Column(db.Boolean)
    tr_vocal    = db.Column(db.Boolean)
    tuning      = db.Column(db.String(40))

    def __init__(self):
        self.last_update = datetime.datetime.utcnow()
        self.dl_count    = 0
        self.tuning      = "E Standard"
        self.tr_guitar   = True
        self.tr_bass     = True
        self.tr_vocal    = True

    def __repr__(self):
        return '<CDLC %r>' % self.id


class Review(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    cdlc_id = db.Column(db.Integer, db.ForeignKey('CDLC.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date    = db.Column(db.DateTime)
    content = db.Column(db.Text)
    score   = db.Column(db.Integer)

    def __repr__(self):
        return '<Review %r>' % self.id



# AUTHENTIFICATION

def get_user_id(username):
    """Convenience method to look up the id for a username."""
    rv = User.query.filter_by(username=username).first()
    return rv.id if rv else None


@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.filter_by(id=session['user_id']).first()


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Logs the user in."""
    if g.user:
        return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user.pw_hash,
                                     request.form['password']):
            error = 'Invalid password'
        else:
            flash('You were logged in')
            session['user_id'] = user.id
            return redirect(url_for('home'))
    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registers the user."""
    if g.user:
        return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to enter a username'
        elif not request.form['email'] or \
                 '@' not in request.form['email']:
            error = 'You have to enter a valid email address'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif get_user_id(request.form['username']) is not None:
            error = 'The username is already taken'
        else:
            newUser = User( request.form['username'],
                            request.form['email'], request.form['password'])
            db.session.add(newUser)
            db.session.commit()
            flash('You were successfully registered and can login now')
            return redirect(url_for('login'))
    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    """Logs the user out."""
    flash('You were logged out')
    session.pop('user_id', None)
    return redirect(url_for('login'))


# THE APP

@app.route('/')
def home():
    """Shows a users timeline or if no user is logged in it will
    redirect to the public timeline.  This timeline shows the user's
    messages as well as all the messages of followed users.
    """
    if not g.user:
        return redirect(url_for('login'))
    # return render_template('home.html', messages=query_db('''
    #     select message.*, user.* from message, user
    #     where message.author_id = user.user_id and (
    #         user.user_id = ? or
    #         user.user_id in (select whom_id from follower
    #                                 where who_id = ?))
    #     order by message.pub_date desc limit ?''',
    #     [session['user_id'], session['user_id'], PER_PAGE]))
    msg = CDLC.query.all()
    for m in msg:
        m.tags = [y.strip() for y in m.tags.split(';')]
    return render_template('home.html', messages=msg)


def parseLastFM(url):
    f       = requests.get(url)

    soup    = bs4.BeautifulSoup(f.content)
    title   = soup.select('h1')[1].select('span')[0].text
    artist  = soup.select('img.crumb-image')[0].parent.text.strip(' \n')
    album   = soup.select('a.media-link-reference')[0].text
    tags    = [x.text for x in soup.select('ul.tags')[0].select('a')]
    artwork = soup.select('img.featured-album')[0]['src']

    c = CDLC()
    c.title   = title
    c.artist  = artist
    c.album   = album
    c.tags    = '; '.join(tags) # [y.strip() for y in x.split(';')] # to rebuild tags
    c.artwork = artwork
    return c

@app.route('/new', methods=['GET', 'POST'])
def newdlc():
    if not g.user:
        return redirect(url_for('login'))

    if request.method == 'GET':
        stub = CDLC()
        if request.args.has_key('lastfm'):
            try:
                stub = parseLastFM(request.args['lastfm'])
            except:
                stub = CDLC()
        elif request.args.has_key('id'):
            stub = CDLC.query.filter_by(id=request.args['id']).first()
            if stub.user_id != g.user.id:
                return "Don't do that !"

        return render_template('newdlc.html', x=stub)

    # handle post
    # todo a bit of checking !!
    cdlc = CDLC()
    flash_m = 'You successfully added a new CDLC'

    # check permissuib
    if request.args.has_key('id'):
        cdlc = CDLC.query.filter_by(id=request.args['id']).first()
        if cdlc.user_id != g.user.id:
            return "Don't do that !"
        else:
            flash_m = request.form['title'] + ' was updated!'

    cdlc.title       = request.form['title']
    cdlc.artist      = request.form['artist']
    cdlc.album       = request.form['album']
    cdlc.tags        = request.form['tags']
    cdlc.year        = request.form['year'] if request.form['year'] != '' else 0
    cdlc.tr_guitar   = request.form.has_key('tr_guitar')
    cdlc.tr_bass     = request.form.has_key('tr_bass')
    cdlc.tr_vocal    = request.form.has_key('tr_vocal')
    cdlc.tuning      = request.form['tuning']
    cdlc.user_id     = g.user.id
    cdlc.artwork     = request.form['artwork']
    cdlc.url_pc      = request.form['url_pc']
    cdlc.url_mac     = request.form['url_mac']
    cdlc.url_xbox    = request.form['url_xbox']
    cdlc.url_ps3     = request.form['url_ps3']
    cdlc.last_update = datetime.datetime.utcnow()

    db.session.add(cdlc)
    db.session.commit()
    flash(flash_m)
    return redirect(url_for('viewdlc', id=cdlc.id))


@app.route('/view', methods=['GET', 'POST'])
def viewdlc():
    if not g.user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        r = Review.query.filter_by(user_id=g.user.id, cdlc_id=request.form['id']).first()
        if r is None:
            r = Review()
            r.user_id = g.user.id
            r.cdlc_id = request.form['id']

        r.content = request.form['newreview_text']
        r.score   = request.form['score']
        r.date    = datetime.datetime.utcnow()

        db.session.add(r)
        db.session.commit()

        flash('Your comment was posted')
        return redirect(url_for('viewdlc', id=request.form['id']))

    stub = CDLC.query.filter_by(id=request.args['id']).first()
    stub.tags = [y.strip() for y in stub.tags.split(';')]
    stub.dlc_creator = User.query.filter_by(id=stub.user_id).first().username

    rs = Review.query.filter_by(cdlc_id=request.args['id']).all()
    score = 0
    if len(rs) > 0:
        for r in rs:
            score += r.score
        score = 1 + score / len(rs)
    # for r in rs:
    #     r['pretty_name'] = User.query.filter_by(id=r['user_id']).first().username
    return render_template('detail.html', x=stub, reviews=rs, score=score)

if __name__ == '__main__':
    db.create_all()
    app.run()