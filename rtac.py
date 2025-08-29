#Carter Keele
#July 2025

from bottle import Bottle, run, route, template, static_file, request, redirect, hook
import requests, json
from beaker.middleware import SessionMiddleware
import re
# import cherrypy

class RTAC():
    def __init__(self, ip, password):
        self.ip = ip
        self.user = 'admin'
        self.password = password
        self.url = 'https://' + self.ip + '/api/v1'
        self.token = ''

app = Bottle()
session_opts = {
    'session.type': 'file',
    'session.cookie_expires': 10800, #Session Time in Seconds 
    'session.data_dir': './data',
    'session.auto': True
}
beaker_app = SessionMiddleware(app, session_opts)

@app.route('/static/<filename>')
def static(filename):
    return static_file(filename, root='./views/static')

@app.route('/')
def rtac_login():
    session = request.environ.get('beaker.session')
    
    if request.GET.btn:
        ip = request.GET.ip
        password = request.GET.password
        rtac = RTAC(ip,password)
        res = requests.get(rtac.url + '/auth/token', verify=False, auth=(rtac.user, rtac.password))
        if res.status_code != 200:
            print('Login Failed')
            return template('login', error = "Login Failed - Try Again")
        res = res.json()
        rtac.token = res.get('AccessToken')
        
        session['rtac_ip'] = rtac.ip
        session['rtac_token'] = rtac.token
        session.save()
        return redirect('/dashboard')
    return template('login')

@app.route('/dashboard', method=['GET','POST'])
def dashboard():    
    session = request.environ.get('beaker.session')
    if not session.get('rtac_ip') or not session.get('rtac_token'):
        session.delete()
        return redirect('/')
    else:
        rtac = RTAC(session.get('rtac_ip'),'')
        rtac.token = session.get('rtac_token')
    
    active = pullData(rtac.url, 'Active', rtac.token)
    active = active.json()
    active_list = active.get('strVal')
    active_list = stringEdit(active_list)
            
    suppressed = pullData(rtac.url, 'Suppressed', rtac.token)
    suppressed = suppressed.json()
    suppressed_list = suppressed.get('strVal')
    suppressed_list = stringEdit(suppressed_list)

    radio = session.get('radio', 'ShowAll') or 'ShowAll'
    search = session.get('search', '') or ''
    
    if radio == None:
        radio = request.forms.get('filterOption') or 'ShowAll'
    if search == None:
        search = request.forms.get('search') or ''
    filter_applied = session.get('filter_applied', False)
    
    if request.method == 'POST':
        checked = request.forms.getall('checkbox')
        action = request.forms.get('action')
        ieds, alarms = splitAlarm(checked)
        print(action)
        
        if action == 'Filter':
            radio = session.get('radio')
            new_radio = request.forms.get('filterOption')
            search = session.get('search')
            new_search = request.forms.get('filterSearch') or ''
            session['radio'] = new_radio
            session['search'] = new_search
            session['filter_applied'] = ((new_radio != 'ShowAll') or bool(new_search))
            session.save()
            
            print(radio)
            print(new_radio)
            print(search)
            print(new_search)
        
        elif action == 'Suppress':
            for ied, alarm in zip(ieds, alarms):
                putData(rtac.url, rtac.token, 'Suppress_IED', ied)
                putData(rtac.url, rtac.token, 'Suppress_Alarm', alarm)
            putData(rtac.url, rtac.token, 'Suppress_IED', '')
            putData(rtac.url, rtac.token, 'Suppress_Alarm', '')
        elif action == 'Clear':
            for ied, alarm in zip(ieds, alarms):
                putData(rtac.url, rtac.token, 'Clear_IED', ied)
                putData(rtac.url, rtac.token, 'Clear_Alarm', alarm)
            putData(rtac.url, rtac.token, 'Clear_IED', '')
            putData(rtac.url, rtac.token, 'Clear_Alarm', '')
        elif action == 'Disconnect':
            session.delete()
            return redirect('/')
        return redirect('/dashboard')        

    filtered_act = [
                item for item in active_list
                if filter(item, radio) and (not search or search.lower() in item.lower())
            ]

    filtered_sup = [
                item for item in suppressed_list
                if filter(item, radio) and (not search or search.lower() in item.lower())
            ]
    print(filtered_act)
    print(filtered_sup)
    print(filter_applied)
    return template('dashboard', 
                    active_list = active_list, 
                    suppressed_list = suppressed_list, 
                    filtered_act = filtered_act, 
                    filtered_sup = filtered_sup, 
                    radio = radio,
                    search = search,
                    filter_applied = filter_applied)

def pullData(url, name, token):
    extension = '/logic-engine/symbols/AlarmGrouping.'
    header = {'Authorization': 'Bearer ' + token}
    return requests.get(url + extension + name, verify=False, headers=header)

def stringEdit(string):
    string = string.split(',')
    string = [i.strip(' ') for i in string]
    return string

def splitAlarm(array):
    temp = []
    ieds = []
    alarms = []
    j = 0
    for i in array:
        temp.append(re.split(': ', i))
        temp[j][0] = temp[j][0].replace('(S) ', '')
        temp[j][0] = temp[j][0].replace('(P) ', '') 
        ieds.append(temp[j][0])
        alarms.append(temp[j][1])
        j+=1
    return ieds, alarms

def putData(url, token, name, data):
    extension = '/logic-engine/symbols/AlarmGrouping.'
    header = {'Authorization': 'Bearer ' + token}
    resGET = pullData(url, name, token)
    resGET = resGET.json()
    resGET['strVal'] = data
    resPUT = requests.put(url + extension + name, verify=False, headers=header, json=resGET)
    print(resPUT)        
    
def filter(item, option):
    if option == 'ShowAll':
        return True
    tag = '(P)' if option == 'ShowP' else '(S)'
    return tag in item

if __name__ == '__main__':
    run(beaker_app, debug=True, reloader=True)