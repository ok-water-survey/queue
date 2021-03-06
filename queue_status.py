import cherrypy
import json, os, math,commands,ast
#import urllib
import pickle
from celery.result import AsyncResult
from celery.execute import send_task
from celery.task.control import inspect
from pymongo import Connection
from datetime import datetime
from Cheetah.Template import Template
from json_handler import handler
from bson.binary import Binary
import config

templatepath= os.path.abspath(os.path.join(os.path.dirname(__file__), 'templates'))

def check_memcache(host='127.0.0.1',port=11211):
    ''' Check if memcache server is running '''
    import socket
    s = socket.socket()
    try:
        s.connect((host,port))
        return True
    except:
        return False

if check_memcache():
    import memcache 
else:
    memcache = None

def update_tasks():
    ''' Enable the use of memcache to save tasks and queues when possible '''
    i = inspect()
    if memcache:
        mc = memcache.Client(['127.0.0.1:11211'])
        tasks = 'REGISTERED_TASKS'
        queues = 'AVAILABLE_QUEUES'
        REGISTERED_TASKS = mc.get(tasks)
        AVAILABLE_QUEUES = mc.get(queues)
        if not REGISTERED_TASKS:
            REGISTERED_TASKS = set()
            for item in i.registered().values():
                REGISTERED_TASKS.update(item)
            mc.set(tasks, REGISTERED_TASKS, 10)
            REGISTERED_TASKS = mc.get('REGISTERED_TASKS')
        if not AVAILABLE_QUEUES:
            mc.set(queues, set([ item[0]['exchange']['name'] for item in i.active_queues().values() ]), 10)
            AVAILABLE_QUEUES = mc.get('AVAILABLE_QUEUES')
    else:
        REGISTERED_TASKS = set()
        for item in i.registered().values():
            REGISTERED_TASKS.update(item)

        AVAILABLE_QUEUES = set([ item[0]['exchange']['name'] for item in i.active_queues().values() ])
    return (REGISTERED_TASKS,AVAILABLE_QUEUES)
            

def mimetype(type):
    def decorate(func):
        def wrapper(*args, **kwargs):
            cherrypy.response.headers['Content-Type'] = type
            return func(*args, **kwargs)
        return wrapper
    return decorate

class Root(object):
    def __init__(self,mongoHost=config.MONGO_HOST,port=config.MONGO_PORT,database=config.MONGO_DATABASE,
                    log_collection=config.MONGO_LOG_COLLECTION,tomb_collection=config.MONGO_TOMB_COLLECTION):
        self.db = Connection(mongoHost,port)#[database]
        self.database = database
        self.collection = log_collection #'ows_task_log'
        self.tomb_collection= tomb_collection #'cybercom_queue_meta'#'okwater'#'cybercom_queue_meta'
    @cherrypy.expose
    @mimetype('text/html')
    def index(self):
        doc = """<html><body><ul><li><a href="report">report</a></li><li><a href="usertasks">tasks</a></li> </ul></body></html>"""
        return doc
    #@cherrypy.expose
    #@mimetype('text/html')
    @cherrypy.expose
    def usertasks(self,task_name=None,pageNumber=1,nPerPage=2500,callback=None,**kwargs):
        ''' usertasks returns celery tasks perform and the link to the task result page.
            task_name-  string optional
            pageNumber and nPerPage is optional
        ''' 
        db=self.db[self.database][self.collection]
        try:
            page=int(pageNumber)
            perPage=int(nPerPage)
        except:
            page=1
            perPage=100
        try:
            if cherrypy.request.login:
                user = cherrypy.request.login
            else:
                user = "guest"
        except:
            pass 
        if not task_name:
            res=db.find({'user':user}).skip((page-1)* int(nPerPage)).limit(int(nPerPage)).sort([('timestamp',-1)]) 
            rows=db.find({'user':user}).count()
        else:
            if task_name[0]=='[':
                res=db.find({'user':user,'task_name':{'$in':ast.literal_eval(task_name)}}).skip((page-1) * int(nPerPage)).limit(int(nPerPage)).sort([('timestamp',-1)])
                rows=db.find({'user':user,'task_name':{'$in':ast.literal_eval(task_name)}}).count()
            else:
                res=db.find({'user':user,'task_name':task_name}).skip((page-1) * int(nPerPage)).limit(int(nPerPage)).sort([('timestamp',-1)])
                rows=db.find({'user':user,'task_name':task_name}).count()
        ePage= int(math.ceil(float(rows)/float(perPage)))
        nameSpace = dict(tasks=res,page=page,endPage=ePage)#tresult)
        #t = Template(file = templatepath + '/usertasks.tmpl', searchList=[nameSpace])
        if callback:
            cherrypy.response.headers['Content-Type'] = 'application/javascript'
            t = Template(file = templatepath + '/usertasks_call.tmpl', searchList=[nameSpace])
            return str(callback) + "(" + json.dumps({'html':t.respond()}) + ")"
        else:
            cherrypy.response.headers['Content-Type'] = 'text/html'
            t = Template(file = templatepath + '/usertasks.tmpl', searchList=[nameSpace])
            return t.respond()
    @cherrypy.expose
    @mimetype('text/html')
    def report(self,taskid=None,callback=None,outtype=None,task=None,**kwargs):
        ''' Generates task result page. This description provides provenance and all information need to rerun tasks
            taskid is required
        '''
                    
        db=self.db[self.database]
        if not taskid:
            try:
                if cherrypy.request.login:
                    user = cherrypy.request.login
                else:
                    user = "guest"
            except:
                pass
            if task:
                query = { 'user': user, 'task_name': task}
            else:
                query = { 'user': user }
            res=db[self.collection].find(query).limit(10).sort([('timestamp',-1)])
            cherrypy.response.headers['Content-Type'] = "application/json"
            return json.dumps([item for item in res], default=handler, indent=2)

        
        res=db[self.collection].find({'task_id':taskid})
        resb = {}
        tresult=db[self.tomb_collection].find({'_id':taskid})
        if not tresult.count() == 0:
            resb['Completed']=str(tresult[0]['date_done'])
            if isinstance(tresult[0]['result'], Binary):
                resb['Result'] = pickle.loads(tresult[0]['result'])
                resb['Traceback'] =pickle.loads( tresult[0]['traceback'])
            else:
                resb['Result']=tresult[0]['result']
                resb['Traceback'] =tresult[0]['traceback']
            try:
                urlcheck = commands.getoutput("wget --spider " + resb['Result'] + " 2>&1| grep 'Remote file exists'")
                if urlcheck:
                    resb['Result']='<a href="' + resb['Result'] + '" target="_blank">' + resb['Result'] + '</a>'
            except:
                pass
            resb['Status'] = tresult[0]['status']

            if isinstance(resb['Result'], type(resb)):
                if 'task_id' in resb['Result']:
                    sub= True
                    sub_taskid = resb['Result']['task_id']
                else:
                    sub = False
                    sub_taskid = None
            else:
                sub= False
                sub_taskid = None
        else:
            sub = False
            sub_taskid = None
        for row in res:
            resclone=row
            for k,v in resclone['kwargs'].items():
                try:
                    temp = ast.literal_eval(v)
                    if type(temp) is dict:
                        hml = "<table class='table table-border'>"
                        for key, val in temp.items():
                            hml = hml + "<tr><td>" + str(key) + "</td><td>" + str(val) + "</td></tr>"
                        hml = hml + "</table>"
                        resclone['kwargs'][k]=hml
                except:
                    pass
        nameSpace = dict(tasks=[resclone],task_id=taskid,tomb=[resb],haschild=sub,sub_taskid=sub_taskid)
        #t = Template(file=templatepath + '/result.tmpl', searchList=[nameSpace])
        if callback and outtype == "json":
            cherrypy.response.headers['Content-Type'] = "application/json"
            return str(callback) + "(" + json.dumps(nameSpace, default=handler, indent=2) + ")"  
        elif outtype == "json":
            cherrypy.response.headers['Content-Type'] = "application/json"
            return json.dumps(nameSpace, default = handler, indent=2)
        else:
            t = Template(file=templatepath + '/result.tmpl', searchList=[nameSpace])
            return t.respond()
    @cherrypy.expose
    @mimetype('text/html')
    def result(self,taskid,callback=None,**kwargs):
        ''' Generates result page. This description provides provenance of tombstone
        '''
        db=self.db[self.database]
        resb = {}
        tresult=db[self.tomb_collection].find({'_id':taskid})
        if not tresult.count() == 0:
            resb['Completed']=str(tresult[0]['date_done'])
            if isinstance(tresult[0]['result'], Binary):
                resb['Result'] = pickle.loads(tresult[0]['result'])
                resb['Traceback'] =pickle.loads( tresult[0]['traceback'])
            else:
                resb['Result']=tresult[0]['result']
                resb['Traceback'] = tresult[0]['traceback']
            try:
                urlcheck = commands.getoutput("wget --spider " + resb['Result'] + " 2>&1| grep 'Remote file exists'")
                if urlcheck:
                    resb['Result']='<a href="' + resb['Result'] + '" target="_blank">' + resb['Result'] + '</a>'
            except:
                pass
            resb['Status'] = tresult[0]['status']
            
        if isinstance(resb['Result'], type(resb)):
            if 'task_id' in resb['Result']:
                sub= True
                sub_taskid = resb['Result']['task_id']
            else:
                sub=False
                sub_taskid = None
        else:
            sub=False
            sub_taskid = None
        nameSpace = dict(tomb=[resb],haschild=sub,sub_taskid=sub_taskid)
        if callback:
            t = Template(file=templatepath + '/tomb_result_call.tmpl', searchList=[nameSpace])
            return str(callback) + "(" + json.dumps({'html':t.respond()}) + ")"
        else:
            t = Template(file=templatepath + '/tomb_result.tmpl', searchList=[nameSpace])
            return t.respond()



    @cherrypy.expose
    @mimetype('application/json')
    def run(self,*args,**kwargs):
        """ Run a celery task from web interface """
        REGISTERED_TASKS,AVAILABLE_QUEUES = update_tasks()
        #return REGISTERED_TASKS
        # If no arguments return list of tasks
        if len(args) == 0:
            return json.dumps({'error': "Unknown task", 'available_tasks': list(REGISTERED_TASKS)}, indent=2)
        funcq = args[0].split('@') #split function queue 
        funcname = funcq[0] # Get function name for calling
        if len(funcq) == 1: # Set default queue to celery if none defined
            queue = 'celery'
        else:
            queue = funcq[1]
        if funcname not in REGISTERED_TASKS: # Check if funcname is know, if not show possible names
            rtasks = list(REGISTERED_TASKS)
            rtasks.sort() 
            return json.dumps({'error': "Unknown task", 'available_tasks': rtasks}, indent=2)
        if queue not in AVAILABLE_QUEUES: # Check if queue is known, if not show possible queue
            aqs = list(AVAILABLE_QUEUES)
            aqs.sort() 
            return json.dumps({'error': "Unknown queue", 'available_queues': aqs}, indent=2)
        funcargs = args[1:] # Slice out function arguments for passing along to task.
        
        if kwargs.has_key('callback'):
            callback = kwargs.pop('callback') # pop off callback so it doesn't get passed to task
            kwargs.pop('_')
        else:
            callback = None
        
        taskobj = send_task( funcname, args=funcargs, kwargs=kwargs, queue=queue, track_started=True )
        #logging tasks performed
        try:
            # Check if user is authenticated with auth_tkt
            if cherrypy.request.login:
                user = cherrypy.request.login
            else:
                user = "Anonymous"
            if 'tags' in kwargs:
                tags = kwargs['tags']
            else:
                tags={}
            task_log = {
                'task_id':taskobj.task_id,
                'user':user,
                'task_name':funcname,
                'args':args,
                'kwargs':kwargs,
                'queue':queue,
                'timestamp':datetime.now(),
                'tags':tags
            }
            self.db[self.database][self.collection].insert(task_log)
        except:
            return json.dumps({'status': "error logging task"})

        if not callback:
            return json.dumps({'task_id':taskobj.task_id}, indent=2)
        else:
            return str(callback) + "(" + json.dumps({'task_id':taskobj.task_id}, indent=2) + ")"



    @cherrypy.expose
    @mimetype('application/json')
    def task(self,task_id=None,type=None,callback=None,**kwargs):
        try:
            if callback == None:
                return self.serialize(task_id,type)
            else:
                return str(callback) + '(' + self.serialize(task_id,type) + ')'
        except Exception as inst:
            #raise inst
            return json.dumps({"status":"Error","Description":str(inst)},indent=2)
    def serialize(self,task_id,type):
        if task_id == None:
            return json.dumps({'available_urls':['/<task_id>/','/<task_id>/status/','/<task_id>/tombstone/']},indent=2)
        if type == None:
            res = {}
            db=self.db[self.database]
            result= db[self.tomb_collection].find_one({'_id':task_id})
            if result:
                res["tombstone"] = [result]
            else:
                res["tombstone"] = [] 
            if len(res['tombstone']) > 0:
                if isinstance(res['tombstone'][0]['result'], Binary):
                    res['tombstone'][0]['result'] = pickle.loads(res['tombstone'][0]['result'])
                    res['tombstone'][0]['traceback'] = pickle.loads(res['tombstone'][0]['traceback'])
                    if 'children' in result:
                        res['tombstone'][0]['children'] = pickle.loads(res['tombstone'][0]['children'])
            res['status']=AsyncResult(task_id).status
            res['task_id']=task_id
            return json.dumps(res,indent=2,default = handler)
        if type.lower() == 'status':
            return json.dumps({"status": AsyncResult(task_id).status},indent=2)
        if type.lower() == 'tombstone':
            res={}
            db=self.db[self.database]
            result= db[self.tomb_collection].find_one({'_id':task_id})
            if result:
                res["tombstone"] = [result]
            else:
                res["tombstone"] = []
            if len(res['tombstone']) > 0:
                if isinstance(res['tombstone'][0]['result'], Binary):
                    res['tombstone'][0]['result'] = pickle.loads(res['tombstone'][0]['result'])
                    res['tombstone'][0]['traceback'] = pickle.loads(res['tombstone'][0]['traceback'])
                    if 'children' in result:
                        res['tombstone'][0]['children'] = pickle.loads(res['tombstone'][0]['children'])
            res['task_id']=task_id
            return json.dumps(res,indent=2,default = handler) 
        if type.lower() == 'result':
            db=self.db[self.database]
            result= db[self.tomb_collection].find_one({'_id':task_id})
            if isinstance(result['result'], Binary):
                return pickle.loads(result['result'])
            else:
                return result['result']
        return json.dumps({'available_urls':['/<task_id>/','/<task_id>/status/','/<task_id>/tombstone/']},indent=2)
cherrypy.tree.mount(Root())
application = cherrypy.tree

if __name__ == '__main__':
    cherrypy.engine.start()
    cherrypy.engine.block()

