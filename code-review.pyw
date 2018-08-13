# -*- coding: UTF-8 -*-

import os
import re
import subprocess as sub
import threadpool
import time
import tkFileDialog
from Tkinter import *
from shutil import copyfile
from tkMessageBox import *

base_dir = ''
diff_dir = ''
last_reviewed_dir = ''
reviewed_commit_record_path = ''
branch = 'master'
THREAD_POOL_SIZE = 5

repo_list_frm = ''
cfg_path = ''


def update_base_dir(base_dir_val):
    global base_dir
    global diff_dir
    global last_reviewed_dir
    global reviewed_commit_record_path
    base_dir = base_dir_val
    diff_dir = base_dir + "/diff"
    last_reviewed_dir = base_dir + "/last-reviewed"
    reviewed_commit_record_path = base_dir + "/last_review.log"
    if os.path.exists(base_dir):
        os.chdir(base_dir_val)


def clear_info():
    sts_text.delete(1.0, END)
    sts_text.update()


def show_info(msg):
    sts_text.insert(END, msg)
    sts_text.see(END)
    sts_text.update()


def show_infon(msg):
    show_info(msg + "\n")


def get_repo_url(base_dir):
    url_dit = {}
    for d in os.listdir(base_dir):
        path = base_dir + '/' + d
        if not os.path.isfile(path) and os.path.exists(path + "/.git"):
            try:
                cmd = "cd %s && git remote -v" % path
                result = sub.check_output(cmd, stderr=sub.STDOUT, shell=True)
                it = result.split("\n")[0].split("\t")[1]
                url = re.sub("\(.*$", "", it)
                url_dit[d] = url.strip()
            except sub.CalledProcessError, exc:
                pass
    return url_dit


def get_latest_log_dict_under_dir(base_dir):
    latest_log_dict = {}
    for d in os.listdir(base_dir):
        path = base_dir + '/' + d
        if not os.path.isfile(path) and os.path.exists(path + "/.git"):
            try:
                latest_log_dict[d] = get_latest_log(path)
            except sub.CalledProcessError, exc:
                pass
    return latest_log_dict


def get_review_record_from_file(lastReviewRecordPath):
    repos = {}
    if not os.path.exists(lastReviewRecordPath):
        return repos
    with open(lastReviewRecordPath, 'r') as f:
        repos = eval(f.read())
    return repos


def save_review_record(repos_record):
    global reviewed_commit_record_path
    with open(reviewed_commit_record_path, 'w') as f:
        f.write(str(repos_record))


def get_repos_path_from_cfg():
    repos = {}
    cfg = cfg_path + '/code-review.cfg'
    if not os.path.exists(cfg):
        print cfg + ' not exist'
        return ''
    with open(cfg, 'r') as f:
        repos = eval(f.read())
    return repos['base_dir']


def save_cfg(repo_base_dir):
    repos = {'base_dir': repo_base_dir}
    with open(cfg_path + '/code-review.cfg', 'w') as f:
        f.write(str(repos))


def checkout_repos(base_dir, repo_commit_id_dict, repo_url_dict):
    latest_func_var = []
    reviewed_func_var = []
    for (repo_name, commit_id) in repo_commit_id_dict.items():
        latest_func_var.append(([base_dir, repo_name, commit_id], None))
        reviewed_func_var.append(
            ([last_reviewed_dir, repo_name, repo_url_dict[repo_name], commit_id['commit_id']], None))
    run_in_thread_pool(checkout_latest, latest_func_var)
    show_infon("get reviewed version")
    run_in_thread_pool(checkout_version, reviewed_func_var)


def checkout_version(base_dir, repo_name, code_url, commit_id):
    checkout_latest(base_dir, repo_name, code_url)
    repo_dir = "%s\\%s" % (base_dir, repo_name)
    cmd = "cd %s && git checkout %s" % (repo_dir, commit_id)
    checkout_result = sub.check_output(cmd, stderr=sub.STDOUT, shell=True)
    print checkout_result


def checkout_latest(base_dir, repo_name, code_url):
    if not os.path.exists(base_dir + r'\\' + repo_name):
        cmd = "cd %s && git clone %s" % (base_dir, code_url)
    else:
        repo_dir = base_dir + "\\" + repo_name
        reset_result = sub.check_output("cd %s && git checkout %s && git reset --hard" % (repo_dir, branch),
                                        stderr=sub.STDOUT, shell=True)
        print reset_result
        cmd = "cd %s && git pull --rebase" % repo_dir
    os.system(cmd)


def get_diff_file_list(repo_path, commit_id_former):
    cmd = "cd %s && git diff --name-only %s" % (repo_path, commit_id_former)
    result = sub.check_output(cmd, stderr=sub.STDOUT, shell=True)
    item = result.strip()
    if re.search('[a-zA-Z]', item):
        file_list = result.strip().split('\n')
    else:
        file_list = []
    return file_list


def diff_repos(repo_name):
    global repos_items_widgets_dict
    latest_dir = "%s\\%s\\latest" % (diff_dir, repo_name)
    reviewed_dir = "%s\\%s\\reviewed" % (diff_dir, repo_name)
    diff_tool_path = r'idea.bat diff'
    cmd = "\"%s\" %s %s" % (diff_tool_path, reviewed_dir, latest_dir)
    repos_items_widgets_dict[repo_name]['review_btn']['bg'] = 'red'
    show_infon(cmd)
    os.system(cmd)
    repos_items_widgets_dict[repo_name]['review_btn']['bg'] = 'gray'


def get_latest_log(repo_dir):
    cmd = "cd " + repo_dir + " && git log -n 1 --pretty=format:\"%ad %an %s\" --date=format:%c"
    result = sub.check_output(cmd, stderr=sub.STDOUT, shell=True)
    return result


def update_repo_commit_id(base_dir, repos_list):
    repos_commit_id_dict = {}
    for r in repos_list:
        cmd = "cd %s\\%s" % (base_dir, r) + " && git log --pretty=format:\"%h\" -n 1"
        result = sub.check_output(cmd, stderr=sub.STDOUT, shell=True)
        if len(result) > 0:
            repos_commit_id_dict[r] = result
    show_infon('update commit history done !')
    return repos_commit_id_dict


def prepare_review(reviewed_commit_id_dict):
    if not os.path.exists(base_dir):
        showerror("Error", "Code root path is blank !")
        return

    global repo_list_frm
    global repos_file_change_number_dict
    start_time = time.time()
    repos_url_dict = get_repo_url(base_dir)
    reviewed_commit_id_dict = get_latest_reviewed_record_from_file(reviewed_commit_record_path)
    repos_latest_log_dict = get_latest_log_dict_under_dir(base_dir)
    if len(reviewed_commit_id_dict) == 0:
        reviewed_commit_id_dict = update_repo_commit_id(base_dir, repos_url_dict.keys())
    checkout_repos(base_dir=base_dir, repo_url_dict=repos_url_dict, repo_commit_id_dict=reviewed_commit_id_dict)
    repos_diff_file_list = get_all_diff_file_list(reviewed_commit_id_dict)

    for (repo, file_list) in repos_diff_file_list.items():
        copy_diff_files(repo, file_list)
        if not repos_file_change_number_dict.has_key(repo):
            repos_file_change_number_dict[repo] = IntVar()
        repos_file_change_number_dict[repo].set(len(file_list))

    clear_repo_review_action_bar()
    create_repo_review_action_bar(repo_list_frm, base_dir, repos_latest_log_dict)

    end_time = time.time()
    time_consum = end_time - start_time
    show_infon('---------------------------------------------------')
    show_infon("Time Cost : %f s" % time_consum)
    show_infon("!!! Prepare Done !!!")
    return reviewed_commit_id_dict


def get_all_diff_file_list(reviewed_commit_id_dict):
    repos_diff_file_list = {}
    for (k, v) in reviewed_commit_id_dict.items():
        repo_path = "%s\\%s" % (base_dir, k)
        repos_diff_file_list[k] = get_diff_file_list(repo_path, v['commit_id'])
    return repos_diff_file_list


def save_file_change_number(lastReviewRecordPath):
    global repos_file_change_number_dict
    repos_record = get_review_record_from_file(lastReviewRecordPath)
    for (k, v) in repos_file_change_number_dict.items():
        repos_record[k]['change'] = v
    save_review_record(repos_record)


def create_reviewed_history():
    if not os.path.exists(base_dir):
        showerror("Error", "Code root path is blank !")
        return

    current_review_record = get_review_record_from_file(reviewed_commit_record_path)
    commit_id_dict = {}
    for d in os.listdir(base_dir):
        path = base_dir + '/' + d
        repo_dict = {}
        if not os.path.isfile(path) and os.path.exists(path + "/.git"):
            try:
                cmd = "cd %s" % path + " && git log --pretty=format:\"%h\" -n 1"
                result = sub.check_output(cmd, stderr=sub.STDOUT, shell=True)
                if len(result) > 0:
                    repo_dict['commit_id'] = result.strip()
                commit_id_dict[d] = repo_dict
            except sub.CalledProcessError, exc:
                pass
    current_review_record[time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())] = commit_id_dict
    save_review_record(current_review_record)
    print 'Review baseline create done !'
    return commit_id_dict


def copy_diff_files(repo_name, file_list):
    dst_base_dir = diff_dir + "/" + repo_name
    try:
        run_copy(base_dir + "/" + repo_name, dst_base_dir + "/latest", file_list)
        run_copy(last_reviewed_dir + "/" + repo_name, dst_base_dir + "/reviewed", file_list)
    except:
        show_infon('copy file error on repo ' + repo_name)


def del_file(path):
    ls = os.listdir(path)
    for i in ls:
        c_path = os.path.join(path, i)
        if os.path.isdir(c_path):
            del_file(c_path)
        else:
            os.remove(c_path)


def run_copy(from_dir, to_dir, file_list):
    if len(file_list) == 0:
        show_infon('no file change')
        return

    if os.path.exists(to_dir):
        del_file(to_dir)
    else:
        os.makedirs(to_dir)
    for f in file_list:
        file_to_dir = to_dir + "/" + os.path.dirname(f)
        if not os.path.exists(file_to_dir):
            os.makedirs(file_to_dir)
            print (file_to_dir)
        to_file_path = to_dir + "/" + f
        from_file_path = from_dir + "/" + f
        if os.path.exists(from_file_path) and os.path.isfile(from_file_path):
            copyfile(from_file_path, to_file_path)
    show_infon("copy %d files from %s to %s" % (len(file_list), from_dir, to_dir))


# 1. 遍历目录收集前一次review的记录
# 2. 拉取最新代码
# 3. 拉取上一次review版本的代码
# 4. 获取change file list
# 5. 复制最新代码和上次review代码
# 6. 比较打开
# 7. 更新review记录

repos_file_change_number_dict = {}


def select_base_dir():
    global repos_base_val
    dir_path = tkFileDialog.askdirectory(title='Open code repos root diretory',
                                         initialdir=os.path.dirname(repos_base_val.get()),
                                         mustexist=True)
    repos_base_val.set(dir_path)
    update_base_dir(dir_path)
    get_repo_url(dir_path)
    save_cfg(dir_path)


def generate_item(frm):
    global new_item_lable
    new_item_lable = Label(frm, text=r"NEW Item")
    new_item_lable.pack(side=LEFT)


def run_in_thread_pool(func_handler, func_var):
    pool = threadpool.ThreadPool(THREAD_POOL_SIZE)
    requests = threadpool.makeRequests(func_handler, func_var)
    [pool.putRequest(req) for req in requests]
    pool.wait()


def clear_repo_review_action_bar():
    global repos_items_widgets_dict
    for (k, v) in repos_items_widgets_dict.items():
        for (key, i) in v.items():
            i.destroy()
    repos_items_widgets_dict.clear()


def create_repo_review_action_bar(repo_list_frm, base_dir, repos_name_list):
    global repos_items_widgets_dict
    global repos_file_change_number_dict
    item_row = 0
    for repo_name in repos_name_list:
        if not repos_file_change_number_dict.has_key(repo_name):
            repos_file_change_number_dict[repo_name] = IntVar()
            repos_file_change_number_dict[repo_name].set(0)
        repo_path = "%s/%s" % (base_dir, repo_name)
        repos_widgets = {}
        col = 0
        repos_widgets['repo_label'] = (
            Label(repo_list_frm, width=30, text=repo_name, justify=LEFT, anchor=W, relief=RAISED))
        repos_widgets['repo_label'].grid(row=item_row, column=col)
        col += 1

        repos_widgets['latest_log'] = (
            Label(repo_list_frm, width=60, text=get_latest_log(repo_path), justify=LEFT, anchor=W, relief=RAISED))
        repos_widgets['latest_log'].grid(row=item_row, column=col)
        col += 1

        repos_widgets['change_file_num'] = (
            Entry(repo_list_frm, width=5, textvariable=repos_file_change_number_dict[repo_name], justify=CENTER,
                  relief=RAISED))
        repos_widgets['change_file_num'].grid(row=item_row, column=col)
        col += 1

        if repos_file_change_number_dict[repo_name].get() > 0:
            color = 'green'
        else:
            color = 'gray'
        repos_widgets['review_btn'] = (Button(repo_list_frm, width=5, text=u"review", bg=color,
                                              command=lambda name=repo_name: diff_repos(name)))
        repos_widgets['review_btn'].grid(row=item_row, column=col)

        repos_items_widgets_dict[repo_name] = repos_widgets
        item_row = item_row + 1


review_record_dict = {}
reviewed_commit_id_dict = {}
repos_items_widgets_dict = {}


def get_latest_reviewed_record_from_file(reviewed_commit_record):
    global review_record_dict
    review_record_dict = get_review_record_from_file(reviewed_commit_record)
    record_time = review_record_dict.keys()
    record_time.reverse()
    return review_record_dict[record_time[0]]


if __name__ == '__main__':
    top = Tk()

    cfg_path = os.path.dirname(sys.argv[0])

    update_base_dir(get_repos_path_from_cfg())
    if os.path.exists(base_dir):
        if not os.path.exists(diff_dir):
            os.mkdir(diff_dir)
        if not os.path.exists(last_reviewed_dir):
            os.mkdir(last_reviewed_dir)
        if not os.path.exists(reviewed_commit_record_path):
            create_reviewed_history()
        review_record_dict = get_review_record_from_file(reviewed_commit_record_path)
        reviewed_commit_id_dict = get_latest_reviewed_record_from_file(reviewed_commit_record_path)

    repos_review = {}

    repos_base_val = StringVar()
    repos_base_val.set(base_dir)

    main_frm = Frame(top)
    review_date = StringVar()
    options = review_record_dict.keys()
    options.sort()
    review_date.set(options[0])
    OptionMenu(main_frm, review_date, *options).pack(side=LEFT)
    Label(main_frm, text=r"Code root path ").pack(side=LEFT)
    Entry(main_frm, textvariable=repos_base_val).pack(side=LEFT)
    Button(main_frm, text=u'..', command=select_base_dir).pack(side=LEFT)
    Button(main_frm, text=u'Get Latest Code !',
           command=lambda reviewed=reviewed_commit_id_dict: prepare_review(reviewed)).pack(side=LEFT)
    Button(main_frm, text=u'Create Review Baseline !', command=create_reviewed_history).pack()
    main_frm.pack()

    repo_list_frm = Frame(top)
    create_repo_review_action_bar(repo_list_frm, base_dir, reviewed_commit_id_dict.keys())
    repo_list_frm.pack()

    sts_frm = Frame(top)
    scr_bar = Scrollbar(sts_frm)
    sts_text = Text(sts_frm, width=100)
    scr_bar.config(command=sts_text.yview)
    sts_text.config(yscrollcommand=scr_bar.set)
    scr_bar.pack(side=RIGHT, fill=Y)
    sts_text.pack()
    sts_frm.pack()

    top.title(u"code review helper")
    top.mainloop()
