#coding=utf-8
from tkinter import *
from tkinter.ttk import *
from tkinter import filedialog, messagebox
import os
import time
import subprocess
import threading
import json
import random
from ast import literal_eval

tk=Tk()
tk.title('defuz')
tk.rowconfigure(0,weight=1)
tk.columnconfigure(1,weight=1)
tk.geometry('450x250')

fnvar=StringVar(value=())
seedvar=StringVar()
tovar=IntVar(value=1000)
cntvar=IntVar(value=20)
loc=''
fns={}

def update():
    fnvar.set(tuple('%s%s'%((v or '').ljust(5,' '),k) for k,v in sorted(fns.items())))

def selectloc(*_,loc_=None):
    global loc
    global fns
    if loc_ is None:
        loc_=filedialog.askdirectory(title='工程目录')
    if not loc_ or not os.path.isdir(loc_):
        return
    loc=loc_
    fns=dict.fromkeys(filter(lambda x:os.path.isfile(os.path.join(loc,x)),os.listdir(loc)))
    try:
        with open(os.path.join(loc,'config.json')) as f:
            conf=json.load(f)
    except Exception:
        pass
    else:
        seedvar.set(conf.get('seed',''))
        tovar.set(conf.get('timeout',1000))
        cntvar.set(conf.get('cnt',20))
        if conf['gen']:
            if conf['gen'] in fns:
                fns[conf['gen']]='gen'
        for fn in conf['stds']:
            if fn in fns:
                fns[fn]='std'
    update()
    locbtn['text']=os.path.split(loc)[1]
    startbtn.state(['!disabled'])

def clicker(*_):
    ind=(lbox.curselection() or [None])[0]
    if ind is not None:
        if literal_eval(fnvar.get())[ind][0]!=' ':
            return
        fn=literal_eval(fnvar.get())[ind][5:]
        if os.path.splitext(fn)[1].lower() not in ('.exe','.py','.bat'):
            return messagebox.showerror('defuz','不支持的文件格式')
        fns[fn]='std' if 'gen' in fns.values() else 'gen'
        update()


def clear(*_):
    global fns
    fns={k:None for k in fns.keys()}
    update()

def execute(exe,timeout,inp):
    killed=False
    def killer():
            nonlocal killed
            killed=True
            p.kill()

    args=[]
    if os.path.splitext(exe)[1]=='.py':
        args=['/c',exe]
        exe='c:/windows/system32/cmd.exe'
    elif os.path.splitext(exe)[1]=='.bat':
        args=['/c',exe]
        exe='c:/windows/system32/cmd.exe'

    p=subprocess.Popen(
        executable=exe,args=args,shell=False,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE
    )
    timer=threading.Timer(timeout,killer)
    t1=time.time()
    if timeout:
        timer.start()

    try:
        pout,perr=p.communicate(inp.encode('gbk','ignore'))
    except OSError:
        return {'error':'无法发送STDIN'}
    else:
        pout=pout.decode('gbk','ignore')
        ret=p.wait()
        t=int(1000*(time.time()-t1))
        timer.cancel()

        if killed or t>timeout*1000:
            return {'error': '运行超时'}
        elif perr:
            print(perr)
            return {'error': 'STDERR不为空'}
        elif ret:
            return {'error': '返回值为%d'%ret}
        else:
            return {'error': None, 'time': t, 'output': pout}

def fuzz(*_):
    gen=[os.path.join(loc,k) for k,v in fns.items() if v=='gen'][0]
    stds=[os.path.join(loc,k) for k,v in fns.items() if v=='std']
    cnt=len(stds)
    timeout=tovar.get()/1000
    if not stds:
        return messagebox.showerror('defuz','没有标程')

    with open(os.path.join(loc,'config.json'),'w') as f:
        json.dump({
            'seed': seedvar.get(),
            'timeout': int(1000*timeout),
            'cnt': cntvar.get(),
            'gen': os.path.basename(gen),
            'stds': [os.path.basename(x) for x in stds],
        },f,indent=4)

    tl=Toplevel(tk)
    tl.title('生成数据 - defuz')
    tl.rowconfigure(0,weight=1)
    tl.columnconfigure(1,weight=1)
    tl.attributes('-topmost',True)
    tl.focus_force()

    def run(*_):
        def _update(i,value):
            detail[i]=value
            tree.item(ind,values=detail)

        def _log(s):
            log.insert(END,str(s)+'\n')
            log.see(END)

        r=random.Random(seedvar.get())
        if not os.path.isdir(os.path.join(loc,'output')):
            os.mkdir(os.path.join(loc,'output'))
        for ind in range(cntvar.get()):
            ind+=1
            rnd=r.randrange(100000000)
            tree.insert('','end',ind,text=rnd)
            tree.see(ind)
            detail=['...']+['']*cnt+['...']
            _log('第 %d 组数据，seed = %d'%(ind,rnd))
            # generate
            _log('  -> 生成数据...')
            res=execute(gen,10,'%d\n%d\n'%(ind,rnd))
            if res['error']:
                _update(0,res['error'])
                _update(-1,'×')
                return _log('数据生成器出现异常')
            else:
                data=res['output']
                _update(0,'%d 字节'%len(data))
            with open(os.path.join(loc,'output/data%d.in'%ind),'wb') as f:
                f.write(data.encode('utf-8',errors='ignore'))
            # run
            result=None
            for stdind,std in enumerate(stds):
                stdind+=1
                _log('  -> 运行第 %d 个标程...'%stdind)
                _update(stdind,'...')
                res=execute(std,timeout,data)
                if res['error']:
                    _update(stdind,res['error'])
                    _update(-1,'×')
                    return _log('标程出现异常')
                if result:
                    if '\n'.join((x.strip() for x in res['output'] if x.strip()))!=result:
                        _update(stdind,'结果不一致')
                        _update(-1,'×')
                        return _log('标程出现异常')
                else:
                    result='\n'.join((x.strip() for x in res['output'] if x.strip()))
                # noinspection PyStringFormat
                _update(stdind,'%d ms'%res['time'])
            # save
            _update(-1,'✓ #%d'%ind)
            with open(os.path.join(loc,'output/data%d.ans'%ind),'wb') as f:
                f.write(res['output'].encode('utf-8',errors='ignore'))
        _log('完成')

    log=Text(tl,width=40)
    log.grid(row=0,column=0,sticky='ns')

    tree=Treeview(tl,columns=('gen',)+tuple(range(cnt))+('result',))
    for i in range(cnt+3):
        tree.column('#%d'%i,width=150,anchor='e')
    tree.heading('#0',text='Seed')
    tree.heading('gen',text=os.path.basename(gen))
    for ind,std in enumerate(stds):
        tree.heading(ind,text=os.path.basename(std))
    tree.heading('result',text='结果')
    tree.grid(row=0,column=1,sticky='nswe')

    threading.Thread(target=run).start()

f=Frame(tk)
f.grid(row=0,column=0,sticky='ns')
f.rowconfigure(4,weight=1)

Label(f,text='工程位置').grid(row=0,column=0)
locbtn=Button(f,text='选择目录……',command=selectloc)
locbtn.grid(row=0,column=1,sticky='we')
Label(f,text='Master Seed').grid(row=1,column=0)
Entry(f,textvariable=seedvar).grid(row=1,column=1)
Label(f,text='标程超时').grid(row=2,column=0)
Entry(f,textvariable=tovar).grid(row=2,column=1)
Label(f,text='数据组数').grid(row=3,column=0)
Entry(f,textvariable=cntvar).grid(row=3,column=1)


startbtn=Button(f,text='生成',command=fuzz)
startbtn.grid(row=5,column=0,columnspan=2)

lbox=Listbox(tk,listvariable=fnvar,font='Consolas -12')
lbox.grid(row=0,column=1,sticky='nswe')
lbox_sbar=Scrollbar(tk,orient=VERTICAL,command=lbox.yview)
lbox_sbar.grid(row=0,column=2,sticky='ns')
lbox['yscrollcommand'] = lbox_sbar.set
lbox.bind('<Double-Button-1>',clicker)
lbox.bind('<Double-Button-3>',clear)

if len(sys.argv)==2:
    init_loc=sys.argv[1]
    if init_loc[0]=='"' and init_loc[-1]=='"':
        init_loc=init_loc[1:-1]
    if os.path.isdir(init_loc):
        tk.after(1,lambda:selectloc(loc_=init_loc))

mainloop()
