from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import flask
import flask_login
import os
import json
import sys
import os
import logging
from app import app,db
from model import User, Envelope, Image, History
from sqlalchemy import func
from hashlib import md5
from itsdangerous import URLSafeTimedSerializer
import datetime


logging.getLogger('flask_cors').level = logging.DEBUG
CORS(app)

app.secret_key = 'snapsend_rocks'
login_serializer = URLSafeTimedSerializer(app.secret_key)

login_manager = flask_login.LoginManager()
login_manager.init_app(app)

#Our mock database.
def datetime_handler(x):
    if isinstance(x, datetime.datetime):
        return x.isoformat()
    raise TypeError("Unknown type")


class User_Class(flask_login.UserMixin):
  def __init__(self, userid, password):
    self.id = userid
    self.password = password


  def get_auth_token(self):
    try:
      data = [str(self.id), self.password]
      return login_serializer.dumps(data)
    except Exception as e:
      return None
    
    


  @staticmethod
  def get(email):

    try:
      user_tuple=User.query.filter_by(email=email).first()
      return User_Class(user_tuple.email,user_tuple.password)
    except:
      return None


def hash_envid(envid):
  target = md5(str(envid).encode('utf-8')).hexdigest()[0:10].upper()
  return target


def hash_pass(password):
    #Return the md5 hash of the password+salt
    if password != "" and password is not None:
      salted_password = password + app.secret_key
      return md5(salted_password).hexdigest()[0:50]
    else:
      return None


@login_manager.request_loader
def load_token(token):
    try:
      data = login_serializer.loads(token)
    except Exception as e:
      return None,1
 
    #Find the User
    user = User_Class.get(data[0])
    if user is None:
      return None,2
 
    #Check Password and return user or None
    if data[1].lower().strip() == user.password.lower().strip():
      return user,0
    else:
      return None,3



@login_manager.user_loader
def load_user(email):
    return User_Class.get(email)



@app.route('/login', methods=['POST'])
def login():
  if request.method == 'POST':
    try:
      loaded_r = request.get_json()
      r = json.dumps(loaded_r)
      loaded_r = json.loads(r)

      email = loaded_r['email']
      pwd = loaded_r['password']
    except Exception as e:
      loaded_r = {"error" : "Accessing the received JSON has failed"}
      return return_success(loaded_r,False)
    
    if pwd is None or pwd == "":
      loaded_r = {"error" : "Password is empty or None"}
      return return_success(loaded_r,False)

    new_pwd = hash_pass(pwd)

    if email == "" or email is None:
      loaded_r = {"error" : "Email ID is empty or None"}
      return return_success(loaded_r,False)


    try:
      user_tuple=User.query.filter_by(email=email).first()
      curr_pwd = user_tuple.password
    except Exception as e:
      loaded_r = {"error" : "User does not exist"}
      return return_success(loaded_r,False)
    

    if new_pwd.lower().strip() == curr_pwd.lower().strip():
      user = User_Class(email,new_pwd)
      flask_login.login_user(user)
      try:
        some_token = user.get_auth_token()
      except Exception as e:
        loaded_r = {"error" : "Token could not be generated"}
        return return_success(loaded_r,False)
      
      try:
        user_tuple.token = some_token
        db.session.commit()
      except Exception as e:
        loaded_r = {"error" : "Generated token could not be added to the database"}
        return return_success(loaded_r,False)
      
      
      loaded_r = {
                  "token" : some_token
                  }
      return return_success(loaded_r,True)

    else:
      loaded_r = {"error" : "Incorrect password"}
      return return_success(loaded_r,False)


@app.route('/signup', methods=['POST'])
def signup():
  if request.method == 'POST':
    try:
      loaded_r = request.get_json()
      r = json.dumps(loaded_r)
      loaded_r = json.loads(r)

      curr_email = loaded_r['email']
      pwd1 = loaded_r['password1']
      pwd2 = loaded_r['password2']
      user_name = loaded_r['username']
      profile_picture = loaded_r['profilepic'] 
    except Exception as e:
      loaded_r = {"error" : "Accessing the received JSON has failed"}
      return return_success(loaded_r,False)


    try:
      hashed_pwd = hash_pass(pwd1)
      if hashed_pwd is None:
        loaded_r = {
                  "error" : "Password is empty or None"
                  }
        return return_success(loaded_r,False)

      if curr_email != "" and curr_email is not None:
        user_obj = User_Class(curr_email,hashed_pwd)
      else:
        loaded_r = {
                  "error" : "Email is empty or None"
                  }
        return return_success(loaded_r,False)

      some_token = user_obj.get_auth_token()
      if some_token is None:
        loaded_r = {
                  "error" : "Token could not be generated"
                  }
        return return_success(loaded_r,False)

      try:
        new_user = User(user_name, curr_email, hashed_pwd, some_token, profile_picture)
        db.session.add(new_user)
        db.session.commit()
      except Exception as e:
        loaded_r = {
                  "error" : "User addition to database failed (pre-existing email ID)"
                  }
        return return_success(loaded_r,False)

      flask_login.login_user(user_obj)

      #passed all cases
      loaded_r = {
                  "token" : some_token 
                  }
      return return_success(loaded_r,True)

    #in case of some other error
    except:
      loaded_r = {
                  "error" : "Signup failed"
                  }

      return return_success(loaded_r,False)



@app.route('/protected')
@flask_login.login_required
def protected():
  return 'Logged in as: ' + flask_login.current_user.id


@app.route('/logout', methods=['POST'])
def logout():
  try:
    loaded_r = request.get_json()
    r = json.dumps(loaded_r)
    loaded_r = json.loads(r)
    tkn = loaded_r['token']
  except Exception as e:
    loaded_r = {"error" : "Accessing the received JSON has failed"}
    return return_success(loaded_r,False)
  
  loaded_usr, code = load_token(tkn)

  if code == 1:
    loaded_r = {"error" : "Invalid token"}
    return return_success(loaded_r,False)

  elif code == 2:
    loaded_r = {"error" : "Getting user data has failed"}
    return return_success(loaded_r,False)

  elif code == 3:
    loaded_r = {"error" : "Login manager password mismatch"}
    return return_success(loaded_r,False)

  elif code == 0:
    loaded_r = {}
    email = loaded_usr.id
    try:
      user_tuple=User.query.filter_by(email=email).first()
      user_tuple.token = None
      db.session.commit()
    except Exception as e:
      loaded_r = {"error" : "Fetching user from database failed"}
      return return_success(loaded_r,False)

    try:
      flask_login.logout_user()
    except Exception as e:
      loaded_r = {"error" : "Login Manager logout failed"}
      return return_success(loaded_r,False)
    
    return return_success(loaded_r,True)



@login_manager.unauthorized_handler
def unauthorized_handler():
  loaded_r = {"error":"Unauthorized User"}
  payload = json.dumps(loaded_r)
  response = make_response(payload)
  response.headers['Content-Type'] = 'text/json'
  return response



@app.route('/helloworld')
def index():
  return "Hello, World"



@app.route('/envelope', methods=['POST'])
def postenvelope():
  loaded_r = request.get_json()
  env_name = loaded_r['envelopeName']
  rec_name = loaded_r['recipientName']
  sender_name = loaded_r['senderName']
  all_images = loaded_r['images']
  token = loaded_r['token']


  j= db.session.query(func.max(Envelope.envelopeID)).scalar()
  if j == None:
    j =0
    h = hash_envid(j+1)
  else: 
    h = hash_envid(j+1)

  if token == None:
    newenvelope = Envelope(env_name,sender_name,rec_name,h)
    newenvelope.eowner = None
    history = History(j+1,'C',None,None)
    db.session.add(history)
    db.session.add(newenvelope)
    db.session.commit()

  else:
    if db.session.query(User).filter_by(token = token).scalar() != None:
      pass
    else:
      payload = {"error":"Invalid token"}
      return return_success(payload,False)
    result = db.session.query(User).filter(User.token==token).first()
    newenvelope = Envelope(env_name,sender_name,rec_name,h)
    newenvelope.eowner = result.userID
    history = History(j+1,'C',result.userID,None)
    db.session.add(history)
    db.session.add(newenvelope)
    db.session.commit()
  
  try:
    for i in range(len(all_images)):
      curr_dict = all_images[i]
      b = curr_dict['url']
      c = curr_dict['filename']
      image = Image(str(j+1),b,c)
      db.session.add(image)
      db.session.commit()

  except Exception as e:
    raise e
  loaded_r['handle'] = h
  return return_success(loaded_r,True)
  


@app.route('/envelope/<handle>', methods=['GET'])
def getenvelope(handle):
  # loaded_r = {"handle": handle}
  # r = json.dumps(loaded_r)
  # loaded_r = json.loads(r)
  # handle = loaded_r['handle']
  if db.session.query(Envelope).filter_by(handle = handle).scalar() != None:
    pass
  else:
    payload = {"error":"Handle does not exist"}
    return return_success(payload,False)
  result = db.session.query(Envelope).filter(Envelope.handle==handle).first()
  envid = result.envelopeID
  imgres = db.session.query(Image).filter(Image.inenvID==envid).all()
  history = db.session.query(History).filter(History.envelopeID==envid).all()
  payload = ""
  env_out = {}
  try:
    env_out = {
        "handle": handle,
        "envelopeName": result.ename,
        "recipientName": result.recipient,
        "senderName": result.sender,
        "createddate":result.createddate
        
    }

    img_arr = []
    img_out = {}

    for imgs in imgres:
      img_out = {"imageId": imgs.imageID, "url": imgs.imagelink, "filename": imgs.filename}
      img_arr.append(img_out)
      img_out = {}

    payload = env_out
    payload["images"] = img_arr

    hist_arr = []
    hist_out = {}
    for hist in history:
      hist_user = hist.userID
      if hist_user != None:
        use = db.session.query(User).filter(User.userID==hist_user).first()
        hist_out = {"action":hist.act_type,"dnum":hist.dnum, "actiondate":hist.actiondate, "username":use.uname}
      else:
        hist_out = {"action":hist.act_type,"dnum":hist.dnum, "actiondate":hist.actiondate, "username":None}
      hist_arr.append(hist_out)
      hist_out = {}

    payload["history"] = hist_arr

    
    
    return return_success(payload,True)

  except Exception as e:
    payload = {"error":str(e)}
    return return_success(payload,False)
    

#@flask_login.login_required
@app.route('/profile/<token>',methods=['GET'])
def profile(token):

  pay = ""
  if db.session.query(User).filter_by(token = token).scalar() != None:
    pass
  else:
    payload = {"error":"Invalid Token"}
    return return_success(payload,False)
  payload ={}
  result1 = db.session.query(User).filter(User.token==token).first()
  payload = {"username":result1.uname,"profilepic":result1.profilepic,"email":result1.email}
  results = db.session.query(History).filter(History.userID==result1.userID).all()

  
  res = []
  for i in results:
    res.append(i.envelopeID)
  
  res = list(set(res))
 
  envelopes = []
  envs = {}
  for r in res:
    result2 = db.session.query(Envelope).filter(Envelope.envelopeID==r).first()
    if result2.eowner == result1.userID:
      envs = {"handle":result2.handle,"senderName":result2.sender,"recipientName":result2.recipient, "envelopeName":result2.ename, "status":"S", "createddate":result2.createddate}
    else:
      envs = {"handle":result2.handle,"senderName":result2.sender,"recipientName":result2.recipient, "envelopeName":result2.ename, "status":"R", "createddate":result2.createddate}
    result3 = db.session.query(Image).filter(Image.inenvID==result2.envelopeID).all()
    img_out = {}
    img_arr = []
    for img in result3:
      img_out = {"imageId": img.imageID, "url": img.imagelink, "filename": img.filename}
      img_arr.append(img_out)
      img_out = {}
    envs["images"] = img_arr
    
    result4 = db.session.query(History).filter(History.envelopeID==result2.envelopeID).all()
    hist_out = {}
    hist_arr =[]
    for hist in result4:
      hist_user = hist.userID
      if hist_user != None:
        use = db.session.query(User).filter(User.userID==hist_user).first()
        hist_out = {"action":hist.act_type,"dnum":hist.dnum, "actiondate":hist.actiondate, "username":use.uname}
      else:
        hist_out = {"action":hist.act_type,"dnum":hist.dnum, "actiondate":hist.actiondate, "username":None}
      hist_arr.append(hist_out)
      hist_out = {}
    envs["history"] = hist_arr
    
    envelopes.append(envs)
    envs = {}

  payload["envelope"]=envelopes
  return return_success(payload,True)



@app.route('/history',methods=['POST'])
def history():
  loaded_r = request.get_json()
  r = json.dumps(loaded_r)
  loaded_r = json.loads(r)
  token = loaded_r['token']
  handle = loaded_r['handle']
  action = loaded_r['action']
  dnum = loaded_r['dnum']
  
  if db.session.query(Envelope).filter(Envelope.handle==handle).scalar() == None:
    payload = {"error":"Invalid Handle"}
    return return_success(payload,False)
  
  result = db.session.query(Envelope).filter(Envelope.handle==handle).first()
  envid = result.envelopeID
  if token != None:
    if db.session.query(User).filter_by(token = token).scalar() != None:
      pass
    else:
      payload = {"error":"Invalid Token"}
      return return_success(payload,False)
    result1 = db.session.query(User).filter(User.token==token).first()

    history = History(envid,action,result1.userID,dnum)
  else:
    history = History(envid,action,None,dnum)
  
  db.session.add(history)
  db.session.commit()
  response = return_success({},True)
  return response

@app.route('/envelope', methods=['DELETE'])
def delete():
  loaded_r = request.get_json()
  r = json.dumps(loaded_r)
  loaded_r = json.loads(r)
  token = loaded_r['token']
  handle = loaded_r['handle']
  if token != None:
    if db.session.query(User).filter_by(token = token).scalar() != None:
      pass
    else:
      payload = {"error":"401 Unauthorised User"}
      return return_success(payload,False)
    if db.session.query(Envelope).filter_by(handle = handle).scalar() != None:
      pass
    else:
      payload = {"error":"Envelope does not exist"}
      return return_success(payload,False)

  env = db.session.query(Envelope).filter(Envelope.handle==handle).first()
  img = db.session.query(Image).filter(Image.inenvID==env.envelopeID).all()
  hist = db.session.query(History).filter(History.envelopeID==env.envelopeID).all()
  for i in img:
    db.session.delete(i)
  for h in hist:
    db.session.delete(h)
  
  db.session.delete(env)
  db.session.commit()
  response = return_success({},True)
  return response


def return_success(loaded_r,j):
  loaded_r['success'] = j
  payload = json.dumps(loaded_r, default=datetime_handler)
  response = make_response(payload)
  response.headers['Content-Type'] = 'text/json'
  response.headers['Access-Control-Allow-Origin'] = '*'
  return response
