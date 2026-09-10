const EMPTY_SUMMARY = {percent: 0, info: '0.00B / 0.00B', speed: '', remaining: ''};

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

function bar(percent, extra) {
    return '<div class="track ' + (extra ? extra : '') + '"><div class="fill" style="width:' + percent + '%"></div></div>';
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

function taskCard(task) {
    var name = task.type ? task.type + ' ' + task.filename : task.filename;
    return '<div class="card">' +
        '<div class="row"><span class="name">' + esc(name) + '</span>' +
        '<span class="pct">' + task.percent + '%</span></div>' +
        bar(task.percent) +
        '<div class="row meta"><span>' + esc(task.info) + '</span><span>' + esc(extraText(task)) + '</span></div>' +
        '</div>';
}

function groupCard(group) {
    var key = group.channel;
    var isCollapsed = collapsed[key] === undefined ? allCollapsed : collapsed[key];
    var html = '<details class="group" data-channel="' + escAttr(key) + '"' + (isCollapsed ? '' : ' open') + '>' +
        '<summary><span class="arrow"></span><span class="gname">' + esc(key) + '</span>' +
        '<span class="gcount">' + group.count + '个</span>' +
        '<span class="pct">' + group.summary.percent + '%</span></summary>' +
        bar(group.summary.percent, 'track-md') +
        '<div class="gmeta"><span>' + esc(group.summary.info) + '</span>' +
        '<span>' + esc(extraText(group.summary)) + '</span></div>';
    for (var i = 0; i < group.tasks.length; i++) {
        html += taskCard(group.tasks[i]);
    }
    return html + '</details>';
}

function doneCard(task) {
    var name = task.type ? task.type + ' ' + task.filename : task.filename;
    var meta = task.channel ? task.info + ' · ' + task.channel : task.info;
    return '<div class="card"><div class="row"><span class="name">' + esc(name) +
        '</span><span class="meta">' + esc(meta) + '</span></div></div>';
}

function linkCard(link) {
    return '<div class="card">' +
        '<div class="mini"><span>' + esc(link.link) + '</span><span class="pct">' +
        link.complete + '/' + link.member + ' · ' + link.percent + '%</span></div>' +
        bar(link.percent) + '</div>';
}

function bindGroups() {
    var nodes = document.querySelectorAll('.group > summary');
    for (var i = 0; i < nodes.length; i++) {
        nodes[i].onclick = function (e) {
            e.preventDefault();
            var details = this.parentNode;
            var key = details.getAttribute('data-channel');
            collapsed[key] = details.open;  // 当前是展开的,点击后记为折叠。
            details.open = !details.open;
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
        collapsed[nodes[i].getAttribute('data-channel')] = allCollapsed;
        nodes[i].open = !allCollapsed;
    }
    syncToggleAll();
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
        document.getElementById('statusText').textContent = '下载中 · ' + taskCount + '个任务';
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
        '<div><span>进行中</span><b>' + data.tasks.length + '</b></div>';
}

function renderList(data) {
    var html = '';
    var i;
    for (i = 0; i < data.groups.length; i++) {
        html += groupCard(data.groups[i]);
    }
    document.getElementById('running').innerHTML = html ? html : '<div class="empty">暂无进行中的任务。</div>';
    bindGroups();
    syncToggleAll();
    html = '';
    for (i = 0; i < data.done.length; i++) {
        html += doneCard(data.done[i]);
    }
    document.getElementById('done').innerHTML = html ? html : '<div class="empty">暂无已完成的任务。</div>';
    html = '';
    for (i = 0; i < data.links.length; i++) {
        html += linkCard(data.links[i]);
    }
    document.getElementById('links').innerHTML = html ? html : '<div class="empty">暂无链接任务。</div>';
}

function renderUploads(uploads) {
    if (uploads.length === 0) {
        document.getElementById('uploads').innerHTML = '<div class="empty">暂无上传任务。</div>';
        return;
    }
    var html = '<div class="card"><table><thead><tr><th>文件</th><th>频道</th><th>大小</th><th>状态</th><th>错误信息</th></tr></thead><tbody>';
    for (var i = 0; i < uploads.length; i++) {
        var task = uploads[i];
        html += '<tr><td>' + esc(task.file) + '</td><td>' + esc(task.chat) + '</td><td>' +
            esc(task.size) + '</td><td>' + esc(task.status) + '</td><td>' + esc(task.error) + '</td></tr>';
    }
    document.getElementById('uploads').innerHTML = html + '</tbody></table></div>';
}

function render(data) {
    renderOverall(data.summary, data.tasks.length);
    renderStat(data);
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

document.getElementById('toggleAll').onclick = toggleAll;
refresh();
setInterval(refresh, 1000);
