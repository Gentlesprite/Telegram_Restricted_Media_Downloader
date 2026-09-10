const EMPTY_SUMMARY = {percent: 0, info: '0.00B / 0.00B', speed: '', remaining: ''};

var TABS = ['running', 'done', 'links', 'uploads'];
var TAB_KEY = 'trmd_tab';

var collapsed = {};
var allCollapsed = false;

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

function pendingRow(item) {
    return '<div class="task-row pending-row">' +
        '<span class="cell-name"><span class="ficon">⏳</span>' +
        '<span class="fname" title="' + escAttr(item.link) + '">' + esc(item.name) + '</span>' +
        (item.channel_name ? '<span class="gcount">' + esc(item.channel_name) + '</span>' : '') +
        '</span>' +
        '<span class="cell-progress"><span class="pct pending">排队中</span></span>' +
        '<span class="cell-size">—</span>' +
        '<span class="cell-speed">—</span>' +
        '<span class="cell-remain">—</span>' +
        '<span class="cell-status status-pending">排队中</span>' +
        '</div>';
}

function groupBlock(group) {
    var key = group.channel;
    var isCollapsed = collapsed[key] === undefined ? allCollapsed : collapsed[key];
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="gname" title="' + escAttr(group.name || key) + '">' + esc(group.name || key) + '</span>' +
        '<span class="gcount">' + group.count + ' 个任务</span></span>' +
        progressCell(group.summary.percent) +
        '<span class="cell-size">' + dash(group.summary.info) + '</span>' +
        '<span class="cell-speed">' + dash(group.summary.speed) + '</span>' +
        '<span class="cell-remain">' + dash(group.summary.remaining) + '</span>' +
        '<span class="cell-status status-running">' + group.count + ' 项</span>' +
        '</div>' +
        '<div class="group-body"' + (isCollapsed ? ' style="display:none"' : '') + '>';
    for (var i = 0; i < group.tasks.length; i++) {
        html += taskRow(group.tasks[i]);
    }
    return html + '</div></div>';
}

function doneRow(task) {
    return '<div class="task-row">' +
        '<span class="cell-name"><span class="ficon">' + esc(task.type || '📄') + '</span>' +
        '<span class="fname" title="' + escAttr(task.filename) + '">' + esc(task.filename) + '</span>' +
        (task.channel_name ? '<span class="gcount">' + esc(task.channel_name) + '</span>' : '') +
        '</span>' +
        progressCell(100) +
        '<span class="cell-size">' + dash(task.info) + '</span>' +
        '<span class="cell-speed">—</span>' +
        '<span class="cell-remain">—</span>' +
        '<span class="cell-status status-done">已完成</span>' +
        '</div>';
}

function linkRow(link) {
    return '<div class="task-row">' +
        '<span class="cell-name"><span class="ficon">🔗</span>' +
        '<span class="fname" title="' + escAttr(link.link) + '">' + esc(link.link) + '</span></span>' +
        progressCell(link.percent) +
        '<span class="cell-size">' + link.complete + '/' + link.member + '</span>' +
        '<span class="cell-speed">—</span>' +
        '<span class="cell-remain">—</span>' +
        '<span class="cell-status ' + (link.remaining ? 'status-pending' : 'status-done') + '">' +
        (link.remaining ? '剩 ' + link.remaining + ' 条' : '已完成') + '</span>' +
        '</div>';
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
    var nodes = document.querySelectorAll('.group');
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

function switchTab(name) {
    if (TABS.indexOf(name) === -1) {
        name = TABS[0];
    }
    var tabs = document.querySelectorAll('.tab');
    for (var i = 0; i < tabs.length; i++) {
        var active = tabs[i].getAttribute('data-tab') === name;
        tabs[i].className = active ? 'tab active' : 'tab';
    }
    for (i = 0; i < TABS.length; i++) {
        document.getElementById('page-' + TABS[i]).hidden = TABS[i] !== name;
    }
    try {
        localStorage.setItem(TAB_KEY, name);
    } catch (e) {
        // 隐私模式下写入失败可忽略。
    }
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

function renderBadges(data) {
    document.getElementById('badgeRunning').textContent = data.tasks.length;
    document.getElementById('badgeDone').textContent = data.done.length;
    document.getElementById('badgeLinks').textContent = data.links.length;
    document.getElementById('badgeUploads').textContent = data.uploads.length;
}

function renderList(data) {
    var html = '';
    var body = '';
    var i;
    for (i = 0; i < (data.pending || []).length; i++) {
        html += pendingRow(data.pending[i]);
    }
    for (i = 0; i < data.groups.length; i++) {
        body += groupBlock(data.groups[i]);
    }
    html += body;
    document.getElementById('running').innerHTML = html ? html : '<div class="empty">暂无进行中的任务。</div>';
    bindGroups();
    syncToggleAll();
    html = '';
    for (i = 0; i < data.done.length; i++) {
        html += doneRow(data.done[i]);
    }
    document.getElementById('done').innerHTML = html ? html : '<div class="empty">暂无已完成的任务。</div>';
    html = '';
    for (i = 0; i < data.links.length; i++) {
        html += linkRow(data.links[i]);
    }
    document.getElementById('links').innerHTML = html ? html : '<div class="empty">暂无链接任务。</div>';
}

function renderUploads(uploads) {
    if (uploads.length === 0) {
        document.getElementById('uploads').innerHTML = '<div class="empty">暂无上传任务。</div>';
        return;
    }
    var html = '<table><thead><tr><th>文件</th><th>频道</th><th>大小</th><th>状态</th><th>错误信息</th></tr></thead><tbody>';
    for (var i = 0; i < uploads.length; i++) {
        var task = uploads[i];
        html += '<tr><td>' + esc(task.file) + '</td><td>' + esc(task.chat) + '</td><td>' +
            esc(task.size) + '</td><td>' + esc(task.status) + '</td><td>' + esc(task.error) + '</td></tr>';
    }
    document.getElementById('uploads').innerHTML = html + '</tbody></table>';
}

function render(data) {
    renderOverall(data.summary, data.tasks.length);
    renderStat(data);
    renderBadges(data);
    renderList(data);
    renderUploads(data.uploads);
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

function bindTabs() {
    var tabs = document.querySelectorAll('.tab');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].onclick = function () {
            switchTab(this.getAttribute('data-tab'));
        };
    }
}

var saved = '';
try {
    saved = localStorage.getItem(TAB_KEY) || '';
} catch (e) {
    saved = '';
}
bindTabs();
switchTab(saved);
document.getElementById('toggleAll').onclick = toggleAll;
refresh();
setInterval(refresh, 1000);
