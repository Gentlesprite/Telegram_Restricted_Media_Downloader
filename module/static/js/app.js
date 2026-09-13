const EMPTY_SUMMARY = {percent: 0, info: '0.00B / 0.00B', speed: '', remaining: ''};

var SECTIONS = {
    download: ['download'],
    upload: ['uploading', 'uploaded', 'upload_failed']
};
var PAGES = SECTIONS.download.concat(SECTIONS.upload);  // 所有页面,下载页不再有分页标签。
var TABS = SECTIONS.upload;  // 顶部分页标签只保留上传的三个页面。
var SECTION_KEY = 'trmd_section';
var TAB_KEY = 'trmd_tab';

var STATE_TEXT = {
    pending: '排队中',
    waiting: '等待中',
    downloading: '下载中',
    success: '已完成',
    skip: '已跳过',
    failure: '失败',
    cancelled: '已取消'
};
var STATE_CLASS = {
    pending: 'status-pending',
    waiting: 'status-pending',
    downloading: 'status-running',
    success: 'status-done',
    skip: 'status-skip',
    failure: 'status-failed',
    cancelled: 'status-pending'
};
var STATE_ICON = {
    pending: '⏳',
    waiting: '⏳',
    downloading: '📥',
    success: '✅',
    skip: '⏭',
    failure: '❌',
    cancelled: '⏸'
};

var collapsed = {};
var allCollapsed = false;
var UNGROUPED_NAME = '未分组';
var currentSection = 'download';
var currentTab = 'download';

function esc(text) {
    var div = document.createElement('div');
    div.textContent = text === undefined || text === null ? '' : text;
    return div.innerHTML;
}

function escAttr(text) {
    return esc(text).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function dash(text) {
    return text ? esc(text) : '—';
}

function progressCell(percent) {
    return '<span class="cell-progress">' +
        '<span class="track"><span class="fill" style="width:' + percent + '%"></span></span>' +
        '<span class="pct">' + percent + '%</span></span>';
}

function taskRow(task) {
    var done = task.percent >= 100;
    return '<div class="task-row">' +
        '<span class="cell-name"><span class="ficon">' + esc(task.type || '📄') + '</span>' +
        '<span class="fname" title="' + escAttr(task.filename) + '">' + esc(task.filename) + '</span></span>' +
        progressCell(task.percent) +
        '<span class="cell-size">' + dash(task.info) + '</span>' +
        '<span class="cell-speed">' + dash(task.speed) + '</span>' +
        '<span class="cell-remain">' + dash(task.remaining) + '</span>' +
        '<span class="cell-status ' + (done ? 'status-done' : 'status-running') + '">' +
        (done ? '已完成' : '下载中') + '</span>' +
        '</div>';
}

function memberRow(item) {
    var state = item.state || 'pending';
    var text = STATE_TEXT[state] || '排队中';
    var cls = STATE_CLASS[state] || 'status-pending';
    var pending = state === 'pending' || state === 'waiting';
    var progress = state === 'success' ? progressCell(100) :
        '<span class="cell-progress"><span class="pct' + (pending ? ' pending' : '') + '">' + text + '</span></span>';
    return '<div class="task-row member-row">' +
        '<span class="cell-name"><span class="ficon">' + (STATE_ICON[state] || '⏳') + '</span>' +
        '<span class="fname" title="' + escAttr(item.name) + '">' + esc(item.name) + '</span>' +
        (item.date ? '<span class="gcount">' + esc(item.date) + '</span>' : '') +
        '</span>' +
        progress +
        '<span class="cell-size">' + dash(item.size) + '</span>' +
        '<span class="cell-speed">—</span>' +
        '<span class="cell-remain">—</span>' +
        '<span class="cell-status ' + cls + '">' + text + '</span>' +
        '</div>';
}

function linkStatusCell(link) {
    var remaining = link.remaining || 0;
    var failed = link.failed || 0;
    if (remaining) {
        return '<span class="cell-status status-pending">剩 ' + remaining + ' 条</span>';
    }
    if (failed) {
        return '<span class="cell-status status-failed">失败 ' + failed + ' 条</span>';
    }
    return '<span class="cell-status status-done">已完成</span>';
}

function getChannelGroups(links) {
    var groups = [];  // 按频道分组下载链接,保持频道首次出现的顺序。
    var index = {};
    var i;
    for (i = 0; i < links.length; i++) {
        var channel = links[i].channel || UNGROUPED_NAME;
        if (index[channel] === undefined) {
            index[channel] = groups.length;
            groups.push({channel: channel, name: '', links: []});
        }
        var group = groups[index[channel]];
        var name = links[i].channel_name || channel;
        if (name.length > group.name.length) {
            group.name = name;  // 同一频道取信息最全的名称,"标题(ID)"比纯ID长。
        }
        group.links.push(links[i]);
    }
    for (i = 0; i < groups.length; i++) {
        var channelGroup = groups[i];
        channelGroup.count = channelGroup.links.length;
        channelGroup.complete = 0;
        channelGroup.member = 0;
        channelGroup.remaining = 0;
        channelGroup.failed = 0;
        for (var j = 0; j < channelGroup.links.length; j++) {
            channelGroup.complete += channelGroup.links[j].complete || 0;
            channelGroup.member += channelGroup.links[j].member || 0;
            channelGroup.remaining += channelGroup.links[j].remaining || 0;
            channelGroup.failed += channelGroup.links[j].failed || 0;
        }
        channelGroup.percent = channelGroup.member ?
            Math.round(channelGroup.complete / channelGroup.member * 1000) / 10 : 0;
    }
    return groups;
}

function channelBlock(group, live) {
    var key = 'channel:' + group.channel;
    var isCollapsed = collapsed[key] === undefined ? allCollapsed : collapsed[key];
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="ficon">📺</span>' +
        '<span class="gname" title="' + escAttr(group.name || group.channel) + '">' +
        esc(group.name || group.channel) + '</span>' +
        '<span class="gcount">' + group.count + ' 个链接</span></span>' +
        progressCell(group.percent) +
        '<span class="cell-size">' + group.complete + '/' + group.member + '</span>' +
        '<span class="cell-speed">—</span>' +
        '<span class="cell-remain">—</span>' +
        linkStatusCell(group) +
        '</div>' +
        '<div class="group-body"' + (isCollapsed ? ' style="display:none"' : '') + '>';
    for (var i = 0; i < group.links.length; i++) {
        html += linkBlock(group.links[i], live);
    }
    return html + '</div></div>';
}

function linkBlock(link, live) {
    var key = 'link:' + link.link;
    var isCollapsed = collapsed[key] === undefined ? true : collapsed[key];  // 链接默认折叠,避免一次性铺开。
    var members = link.queue || [];
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="ficon">🔗</span>' +
        '<span class="fname" title="' + escAttr(link.link) + '">' + esc(link.link) + '</span>' +
        '<span class="gcount">' + (link.queue_total || 0) + ' 条未完成 / 共 ' + (link.total || 0) + ' 条</span></span>' +
        progressCell(link.percent) +
        '<span class="cell-size">' + link.complete + '/' + link.member + '</span>' +
        '<span class="cell-speed">—</span>' +
        '<span class="cell-remain">—</span>' +
        linkStatusCell(link) +
        '</div>' +
        '<div class="group-body"' + (isCollapsed ? ' style="display:none"' : '') + '>';
    for (var i = 0; i < members.length; i++) {
        var member = members[i];
        var task = member.state === 'downloading' ? live[member.task_id] : null;
        html += task ? taskRow(task) : memberRow(member);  // 下载中的成员直接复用进度条任务行。
    }
    if (members.length === 0) {
        html += '<div class="more">该链接暂无消息。</div>';
    }
    return html + '</div></div>';
}

function bindGroups() {
    var nodes = document.querySelectorAll('.group-head');
    for (var i = 0; i < nodes.length; i++) {
        nodes[i].onclick = function () {
            var group = this.parentNode;
            var key = this.getAttribute('data-channel');
            var body = group.querySelector('.group-body');
            var hide = body.style.display !== 'none';  // 当前是展开的,点击后折叠。
            body.style.display = hide ? 'none' : '';
            group.className = hide ? 'group' : 'group open';
            collapsed[key] = hide;
        };
    }
}

function syncToggleAll() {
    document.getElementById('toggleAll').textContent = allCollapsed ? '全部展开' : '全部折叠';
}

function toggleAll() {
    var nodes = document.querySelectorAll('#download .group');  // 只切换下载页的分组。
    allCollapsed = !allCollapsed;
    for (var i = 0; i < nodes.length; i++) {
        var key = nodes[i].getAttribute('data-channel');
        var body = nodes[i].querySelector('.group-body');
        body.style.display = allCollapsed ? 'none' : '';
        nodes[i].className = allCollapsed ? 'group' : 'group open';
        collapsed[key] = allCollapsed;
    }
    syncToggleAll();
}

function sectionOfTab(name) {
    for (var key in SECTIONS) {
        if (SECTIONS[key].indexOf(name) !== -1) {
            return key;
        }
    }
    return 'download';
}

function saveState(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (e) {
        // 隐私模式下写入失败可忽略。
    }
}

function applySection() {
    var items = document.querySelectorAll('.side-item');
    for (var i = 0; i < items.length; i++) {
        var active = items[i].getAttribute('data-section') === currentSection;
        items[i].className = active ? 'side-item active' : 'side-item';
    }
    document.getElementById('tabs').hidden = currentSection !== 'upload';  // 只有上传区有分页标签。
    document.getElementById('downloadSummary').hidden = currentSection !== 'download';
}

function applyTab() {
    var tabs = document.querySelectorAll('.tab');
    for (var i = 0; i < tabs.length; i++) {
        var active = tabs[i].getAttribute('data-tab') === currentTab;
        tabs[i].className = active ? 'tab active' : 'tab';
    }
    for (i = 0; i < PAGES.length; i++) {
        document.getElementById('page-' + PAGES[i]).hidden = PAGES[i] !== currentTab;
    }
}

function switchSection(name) {
    if (!SECTIONS[name]) {
        name = 'download';
    }
    currentSection = name;
    if (SECTIONS[currentSection].indexOf(currentTab) === -1) {
        currentTab = SECTIONS[currentSection][0];  // 切区后当前子页不属于该区时回到首个子页。
    }
    applySection();
    applyTab();
    saveState(SECTION_KEY, currentSection);
    saveState(TAB_KEY, currentTab);
}

function switchTab(name) {
    if (PAGES.indexOf(name) === -1) {
        name = PAGES[0];
    }
    currentSection = sectionOfTab(name);
    currentTab = name;
    applySection();
    applyTab();
    saveState(SECTION_KEY, currentSection);
    saveState(TAB_KEY, currentTab);
}

function extraText(item) {
    var extra = '';
    if (item.speed) {
        extra += item.speed;
    }
    if (item.remaining) {
        extra += (extra ? ' · 剩余' : '剩余') + item.remaining;
    }
    return extra;
}

function renderOverall(summary, taskCount) {
    var data = summary || EMPTY_SUMMARY;
    document.getElementById('overallFill').style.width = data.percent + '%';
    document.getElementById('overallPercent').textContent = data.percent + '%';
    document.getElementById('overallInfo').textContent = data.info;
    document.getElementById('overallExtra').textContent =
        extraText(data) ? extraText(data) : (taskCount ? '正在测速' : '暂无速度');
    if (taskCount > 0) {
        document.getElementById('dot').className = 'dot active';
        document.getElementById('statusText').textContent = '下载中 · ' + taskCount + ' 个任务';
    } else {
        document.getElementById('dot').className = 'dot';
        document.getElementById('statusText').textContent = '空闲 · 等待任务';
    }
}

function renderStat(data) {
    document.getElementById('stat').innerHTML =
        '<div><span>成功</span><b class="ok">' + data.count.success + '</b></div>' +
        '<div><span>失败</span><b class="bad">' + data.count.failure + '</b></div>' +
        '<div><span>跳过</span><b class="skip">' + data.count.skip + '</b></div>' +
        '<div><span>进行中</span><b>' + data.tasks.length + '</b></div>' +
        '<div><span>队列中</span><b class="queue">' + (data.queue || 0) + '</b></div>';
}

function renderBadges(data, counted) {
    document.getElementById('badgeDownload').textContent = data.tasks.length;
    document.getElementById('badgeUploading').textContent = counted.uploading;
    document.getElementById('badgeUploaded').textContent = counted.uploaded;
    document.getElementById('badgeUploadFailed').textContent = counted.failed;
}

function renderList(data) {
    var live = {};  // 进度条任务ID -> 任务,供下载中的成员复用实时进度。
    var i;
    for (i = 0; i < (data.tasks || []).length; i++) {
        live[data.tasks[i].id] = data.tasks[i];
    }
    var html = '';
    var groups = getChannelGroups(data.links || []);  // 频道 > 链接 > 下载信息,两级可折叠。
    for (i = 0; i < groups.length; i++) {
        html += channelBlock(groups[i], live);
    }
    document.getElementById('download').innerHTML = html ? html : '<div class="empty">暂无下载任务。</div>';
    syncToggleAll();
    bindGroups();  // 页面渲染完成后统一绑定折叠事件。
}

function uploadList(tasks) {
    if (tasks.length === 0) {
        return '<div class="empty">暂无上传任务。</div>';
    }
    var html = '<table><thead><tr><th>文件</th><th>频道</th><th>大小</th><th>状态</th><th>错误信息</th></tr></thead><tbody>';
    for (var i = 0; i < tasks.length; i++) {
        var task = tasks[i];
        html += '<tr><td>' + esc(task.file) + '</td><td>' + esc(task.chat) + '</td><td>' +
            esc(task.size) + '</td><td>' + esc(task.status) + '</td><td>' + esc(task.error) + '</td></tr>';
    }
    return html + '</tbody></table>';
}

function renderUploads(uploads) {
    var uploading = [];
    var uploaded = [];
    var failed = [];
    for (var i = 0; i < uploads.length; i++) {
        var state = uploads[i].state;
        if (state === 'failure') {
            failed.push(uploads[i]);
        } else if (state === 'success' || state === 'sent') {
            uploaded.push(uploads[i]);
        } else {
            uploading.push(uploads[i]);
        }
    }
    document.getElementById('uploading').innerHTML = uploadList(uploading);
    document.getElementById('uploaded').innerHTML = uploadList(uploaded);
    document.getElementById('upload_failed').innerHTML = uploadList(failed);
    return {uploading: uploading.length, uploaded: uploaded.length, failed: failed.length};
}

function render(data) {
    renderOverall(data.summary, data.tasks.length);
    renderStat(data);
    var counted = renderUploads(data.uploads);
    renderBadges(data, counted);
    renderList(data);
}

async function refresh() {
    try {
        var res = await fetch('/api/progress', {cache: 'no-store'});
        render(await res.json());
        document.getElementById('offline').style.display = 'none';
    } catch (e) {
        document.getElementById('offline').style.display = 'block';
    }
}

function bindSections() {
    var items = document.querySelectorAll('.side-item');
    for (var i = 0; i < items.length; i++) {
        items[i].onclick = function () {
            switchSection(this.getAttribute('data-section'));
        };
    }
}

function bindTabs() {
    var tabs = document.querySelectorAll('.tab');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].onclick = function () {
            switchTab(this.getAttribute('data-tab'));
        };
    }
}

var savedSection = '';
var savedTab = '';
try {
    savedSection = localStorage.getItem(SECTION_KEY) || '';
    savedTab = localStorage.getItem(TAB_KEY) || '';
} catch (e) {
    savedSection = '';
    savedTab = '';
}
bindSections();
bindTabs();
if (savedTab && PAGES.indexOf(savedTab) !== -1) {
    switchTab(savedTab);
} else {
    switchSection(savedSection);
}
document.getElementById('toggleAll').onclick = toggleAll;
refresh();
setInterval(refresh, 1000);
