import cherrypy
import json 
import urllib
from celery.result import AsyncResult
from cybercomq.model.teco import task

def mimetype(type):
    def decorate(func):
        def wrapper(*args, **kwargs):
            cherrypy.response.headers['Content-Type'] = type
            return func(*args, **kwargs)
        return wrapper
    return decorate

class Root(object):
    @cherrypy.expose
    def index(self):
        return None
    @cherrypy.expose
    @mimetype('application/json')
    def teco(self,task_type,**kwargs):
        if task_type.upper() == 'SETINPUT':
            res = task.getTecoinput.apply_async([],queue='celery')
            return json.dumps({'task_id':res.task_id},indent=2)#res.task_id
        if task_type.upper() == 'RUN':
            res= task.runTeco.apply_async(["f"],queue='celery')   
            return json.dumps({'task_id':res.task_id},indent=2)#res.task_id
        return json.dumps({'available_options':['run','setinput']},indent=2)
        
    @cherrypy.expose
    @mimetype('application/json')
    def task(self,task_id=None,type=None,**kwargs):
        if task_id == None:
            return json.dumps({'available_urls':['/<task_id>/','/<task_id>/status/','/<task_id>/tombstone/']},indent=2)
        if type == None:
            res = {}
            result = urllib.urlopen("http://fire.rccc.ou.edu/mongo/db_find/cybercom_queue/cybercom_queue_meta/{'spec':{'_id':'" + task_id + "'}}")
            res["tombstone"]=json.loads(result.read())
            res['status']=AsyncResult(task_id).status
            res['task_id']=task_id
            return json.dumps(res,indent=2)
        if type.lower() == 'status':
            return json.dumps({"status": AsyncResult(task_id).status},indent=2)
        if type.lower() == 'tombstone':
            res={}
            result = urllib.urlopen("http://fire.rccc.ou.edu/mongo/db_find/cybercom_queue/cybercom_queue_meta/{'spec':{'_id':'" + task_id + "'}}")
            res['tombstone']=json.loads(result.read())
            res['task_id']=task_id            
            return json.dumps(res,indent=2) #result.read()
        return json.dumps({'available_urls':['/<task_id>/','/<task_id>/status/','/<task_id>/tombstone/']},indent=2)
cherrypy.tree.mount(Root())
application = cherrypy.tree

if __name__ == '__main__':
    cherrypy.engine.start()
    cherrypy.engine.block()

