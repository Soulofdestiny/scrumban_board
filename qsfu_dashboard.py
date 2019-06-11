#!/usr/bin/env python3
#==============================================================================

from redminelib import Redmine
import pdb
import datetime
import logging
import json
import statistics
import configparser
import matplotlib
import matplotlib.pyplot as plt
from flask import Flask, render_template, redirect, url_for
import time
import atexit
from apscheduler.schedulers.background import BackgroundScheduler



app = Flask(__name__)


config = configparser.ConfigParser()
config.read('config_kanban.ini')

URL = config['API']['URL']
KEY = config['API']['ApiKey']


redmine = Redmine(URL, key=KEY)

prjlist = ['suseqa', 'openqav3', 'openqatests']
taglist = ['y', 'epic', 'saga', 'fate']

id_codes = {
        'New' : '1',
        'In Progress' : '2',
        'Resolved' : '3',
        'Feedback' : '4',
        'Workable' : '12'
        }

def date_time():
    return time.strftime("%A, %d. %B %Y %I:%M:%S %p")

def went_in_progress(jsn):
    if jsn.get("name", "invalid_default") == "status_id":
        if jsn["new_value"] == id_codes.get("In Progress"):
            return jsn["old_value"] in [id_codes["Workable"], id_codes["New"]]
    return False

def is_story(tckt):
    if any(s in tckt.subject for s in taglist):
        return False
    return True

def get_stats():
    cycleList = []
    leadList = []
    print('generating new data...')
    for prj in prjlist:
        tickets = redmine.issue.filter(project_id=prj, status_id=id_codes["Resolved"])
        #tickets = redmine.issue.filter(project_id='QA', status_id=id_codes["Resolved"])
        u_tickets = [t for t in tickets if '[u]' in t.subject]
        for tckt in u_tickets:
            # only consider normal [u] tickets
            if not is_story(tckt):
                continue

            #try:
            #    print(t.subject)
            #except:
            #    print("Could not print subject")

            crtDate = tckt.created_on
            endDate = tckt.closed_on
            # set an invalid default
            prgDate = None

            #print("Creation date: " + str(crtDate))
            #print("Close date: " + str(endDate))

            journals = tckt.journals
            for jrn in journals:
                try:
                    # look at first entry to not get an array
                    jDetails = json.loads(json.dumps(jrn.details[0]))
                except:
                    # empty details
                    continue
                if went_in_progress(jDetails):
                    prgDate = jrn.created_on
                    #print("Went in progress: " + str(prgDate))
                    break

            leadTime = endDate - crtDate
            #print("Lead time " + str(leadTime))
            leadList.append(leadTime.days)

            if prgDate:
                cycTime = endDate - prgDate
                #print("Cycle time: " + str(cycTime))
                cycleList.append(cycTime.days)

    meanCycTime = statistics.mean(cycleList)
    medianCycTime = statistics.median(cycleList)

    meanLeadTime = statistics.mean(leadList)
    medianLeadTime = statistics.median(leadList)

    global raw_data
    raw_data = {
            'meta' : {
                'current_time' : date_time()
                },
            'metrics' : {
                'mean-cycle' : str(meanCycTime),
                'median-cycle' : str(medianCycTime),
                'min-cycle' : str(min(cycleList)),
                'max-cycle' : str(max(cycleList)),
                'mean-lead' : str(meanLeadTime),
                'median-lead' : str(medianLeadTime),
                'min-lead' : str(min(leadList)),
                'max-lead' : str(max(leadList)),
                'total-tickets' : str(len(u_tickets))
                }
            }

    plot_lead(leadList)
    plot_cycle(cycleList)

    print('new data created @', date_time())


def plot_cycle(cycleList):
    plt.figure(1)
    plt.hist(cycleList)
    plt.ylabel("Amount of tickets")
    plt.xlabel("Cycletime in days")
    plt.savefig('static/images/plot_cycle.svg')


def plot_lead(leadList):
    plt.figure(2)
    plt.subplot(111)
    plt.hist(leadList)
    plt.ylabel("Amount of tickets")
    plt.xlabel("Leadtime in days")
    plt.savefig('static/images/plot_lead.svg')

@app.route('/')
def index():
    return render_template('plot.html', name='plot', url_lead='static/images/plot_lead.svg', url_cycle='static/images/plot_cycle.svg', t=raw_data['meta']['current_time'], data=raw_data)

def test_scheduler():
    print('scheduler ran @', date_time())

scheduler = BackgroundScheduler()
scheduler.add_job(func=get_stats, trigger="interval", minutes=10)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

get_stats()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug = False)
