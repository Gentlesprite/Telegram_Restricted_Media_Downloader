const EMPTY_SUMMARY = {percent: 0, info: '0.00B / 0.00B', speed: '', remaining: ''};

var SECTIONS = {
    download: ['download'],
    upload: ['upload']
};
var PAGES = SECTIONS.download.concat(SECTIONS.upload);  // 下载、上传各一个页面,均不再有分页标签。
var SUMMARY_IDS = {
    download: {fill: 'overallFill', percent: 'overallPercent', info: 'overallInfo', extra: 'overallExtra'},
    upload: {fill: 'uploadFill', percent: 'uploadPercent', info: 'uploadInfo', extra: 'uploadExtra'}
};  // 下载与上传各自独立的总进度面板,避免相互覆盖。
var SECTION_KEY = 'trmd_section';

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

var HEAD_LABELS = ['频道', '频道 / 链接', '频道 / 链接 / 名称'];  // 表头首列随当前展开的层级变化。
var SIZE_LABELS = ['完成 / 总数', '完成 / 总数', '数量 / 大小'];  // 第三列同理,分组行是数量,成员行才是字节大小。
var UPLOAD_HEAD_NAME = ['频道', '频道 / 文件路径'];  // 上传页只有频道与文件两级。
var UPLOAD_HEAD_SIZE = ['完成 / 总数', '大小'];
var UPLOAD_TEXT = {
    pending: '排队中',
    uploading: '上传中',
    success: '已完成',
    sent: '已完成',
    failure: '失败'
};
var UPLOAD_CLASS = {
    pending: 'status-pending',
    uploading: 'status-running',
    success: 'status-done',
    sent: 'status-done',
    failure: 'status-failed'
};
var UPLOAD_ICON = {
    pending: '⏳',
    uploading: '📤',
    success: '✅',
    sent: '✅',
    failure: '❌'
};
var collapsed = {};
var allCollapsed = false;
var uploadAllCollapsed = false;
var UNGROUPED_NAME = '未分组';
var currentSection = 'download';
var lastDownloadActive = 0;
var lastUploadActive = 0;

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

var SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];  // 与终端的十进制单位保持一致。

function sizeText(bytes) {
    var value = Number(bytes) || 0;
    var index = 0;
    while (value >= 1000 && index < SIZE_UNITS.length - 1) {
        value = value / 1000;
        index++;
    }
    return value.toFixed(2) + SIZE_UNITS[index];
}

function secondsText(seconds) {
    var total = Math.floor(Number(seconds) || 0);
    if (total < 60) {
        return total + '秒';
    }
    if (total < 3600) {
        return Math.floor(total / 60) + '分' + (total % 60) + '秒';
    }
    return Math.floor(total / 3600) + '时' + Math.floor(total % 3600 / 60) + '分' + (total % 60) + '秒';
}

function groupStat(members, live) {
    var speed = 0;
    var left = 0;
    for (var i = 0; i < members.length; i++) {
        var member = members[i];
        var task = live[member.task_id] || member;  // 上传成员自带进度字段,查不到进度条任务时回退到自身。
        if (member.state === 'success' || member.state === 'skip' || member.state === 'sent') {
            continue;  // 已完成、已跳过、已发送的成员不再计入速度与剩余。
        }
        if (task && task.speed_value) {
            speed += Number(task.speed_value) || 0;
        }
        left += Math.max((Number(member.size_byte) || 0) - (Number(task && task.completed) || 0), 0);
    }
    return {speed: speed, remaining: speed && left > 0 ? left / speed : null};
}

function groupStatCells(stat) {
    var speed = stat.speed ? sizeText(stat.speed) + '/s' : '—';
    var remain = stat.remaining === null ? '—' : secondsText(stat.remaining);
    return '<span class="cell-speed">' + speed + '</span>' +
        '<span class="cell-remain">' + remain + '</span>';
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
        channelGroup.members = [];  // 汇总该频道下所有链接的成员,用于计算频道级速度与剩余时间。
        for (var j = 0; j < channelGroup.links.length; j++) {
            channelGroup.complete += channelGroup.links[j].complete || 0;
            channelGroup.member += channelGroup.links[j].member || 0;
            channelGroup.remaining += channelGroup.links[j].remaining || 0;
            channelGroup.failed += channelGroup.links[j].failed || 0;
            channelGroup.members = channelGroup.members.concat(channelGroup.links[j].queue || []);
        }
        channelGroup.percent = channelGroup.member ?
            Math.round(channelGroup.complete / channelGroup.member * 1000) / 10 : 0;
    }
    return groups;
}

function channelBlock(group, live) {
    var key = 'channel:' + group.channel;
    var isCollapsed = collapsed[key] === undefined ? allCollapsed : collapsed[key];
    var stat = groupStat(group.members || [], live);
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '" data-level="1">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="ficon">📺</span>' +
        '<span class="gname" title="' + escAttr(group.name || group.channel) + '">' +
        esc(group.name || group.channel) + '</span>' +
        '<span class="gcount">' + group.count + ' 个链接</span></span>' +
        progressCell(group.percent) +
        '<span class="cell-size">' + group.complete + '/' + group.member + '</span>' +
        groupStatCells(stat) +
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
    var stat = groupStat(members, live);
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '" data-level="2">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="ficon">🔗</span>' +
        '<span class="fname" title="' + escAttr(link.link) + '">' + esc(link.link) + '</span>' +
        '<span class="gcount">' + (link.queue_total || 0) + ' 条未完成 / 共 ' + (link.total || 0) + ' 条</span></span>' +
        progressCell(link.percent) +
        '<span class="cell-size">' + link.complete + '/' + link.member + '</span>' +
        groupStatCells(stat) +
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

function groupVisible(node) {
    for (var parent = node.parentNode; parent; parent = parent.parentNode) {
        if (parent.style && parent.style.display === 'none') {
            return false;  // 任一层祖先被折叠,该分组即不可见。
        }
    }
    return true;
}

function syncHeadLabel() {
    var level = 1;
    var nodes = document.querySelectorAll('#download .group.open');
    for (var i = 0; i < nodes.length; i++) {
        var depth = nodes[i].getAttribute('data-level') === '2' ? 3 : 2;
        if (depth > level && groupVisible(nodes[i])) {
            level = depth;  // 取当前可见的最深层级。
        }
    }
    document.getElementById('headName').textContent = HEAD_LABELS[level - 1];
    document.getElementById('headSize').textContent = SIZE_LABELS[level - 1];  // 分组行是条数,成员行才是字节。
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
            syncHeadLabel();
            syncUploadHeads();
        };
    }
}

function syncToggleAll() {
    document.getElementById('toggleAll').textContent = allCollapsed ? '全部展开' : '全部折叠';
}

function syncToggleUpload() {
    document.getElementById('toggleUpload').textContent = uploadAllCollapsed ? '全部展开' : '全部折叠';
}

function setAllGroups(selector, hide) {
    var nodes = document.querySelectorAll(selector + ' .group');
    for (var i = 0; i < nodes.length; i++) {
        var key = nodes[i].getAttribute('data-channel');
        var body = nodes[i].querySelector('.group-body');
        body.style.display = hide ? 'none' : '';
        nodes[i].className = hide ? 'group' : 'group open';
        collapsed[key] = hide;
    }
}

function toggleAll() {
    allCollapsed = !allCollapsed;
    setAllGroups('#download', allCollapsed);
    syncToggleAll();
    syncHeadLabel();
}

function toggleUploadAll() {
    uploadAllCollapsed = !uploadAllCollapsed;
    setAllGroups('#upload', uploadAllCollapsed);
    syncToggleUpload();
    syncUploadHeads();
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
    document.getElementById('downloadSummary').hidden = currentSection !== 'download';
    document.getElementById('uploadSummary').hidden = currentSection !== 'upload';  // 两个板块各自独立的总进度。
    for (i = 0; i < PAGES.length; i++) {
        document.getElementById('page-' + PAGES[i]).hidden = PAGES[i] !== currentSection;
    }
    renderStatus();
}

function switchSection(name) {
    if (!SECTIONS[name]) {
        name = 'download';
    }
    currentSection = name;
    applySection();
    saveState(SECTION_KEY, currentSection);
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

function renderOverall(summary, taskCount, ids) {
    var data = summary || EMPTY_SUMMARY;
    document.getElementById(ids.fill).style.width = data.percent + '%';
    document.getElementById(ids.percent).textContent = data.percent + '%';
    document.getElementById(ids.info).textContent = data.info;
    document.getElementById(ids.extra).textContent =
        extraText(data) ? extraText(data) : (taskCount ? '正在测速' : '暂无速度');
}

function statCell(label, value, cls) {
    return '<div><span>' + label + '</span><b' + (cls ? ' class="' + cls + '"' : '') + '>' +
        value + '</b></div>';
}

function renderStat(id, cells) {
    document.getElementById(id).innerHTML = cells.join('');
}

function renderStatus() {
    var count = currentSection === 'upload' ? lastUploadActive : lastDownloadActive;
    if (count > 0) {
        document.getElementById('dot').className = 'dot active';
        document.getElementById('statusText').textContent =
            (currentSection === 'upload' ? '上传中 · ' : '下载中 · ') + count + ' 个任务';
    } else {
        document.getElementById('dot').className = 'dot';
        document.getElementById('statusText').textContent = '空闲 · 等待任务';
    }
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
    syncHeadLabel();
}

function uploadDone(file) {
    return file.state === 'success' || file.state === 'sent';
}

function getUploadGroups(tasks) {
    var groups = [];  // 按频道分组上传任务,保持频道首次出现的顺序。
    var index = {};
    var i;
    for (i = 0; i < tasks.length; i++) {
        var channel = tasks[i].channel || UNGROUPED_NAME;
        if (index[channel] === undefined) {
            index[channel] = groups.length;
            groups.push({channel: channel, name: tasks[i].chat || channel, files: []});
        }
        groups[index[channel]].files.push(tasks[i]);
    }
    for (i = 0; i < groups.length; i++) {
        var group = groups[i];
        group.count = group.files.length;
        group.complete = 0;
        group.failed = 0;
        group.total_byte = 0;
        group.done_byte = 0;
        for (var j = 0; j < group.files.length; j++) {
            var file = group.files[j];
            if (file.state === 'failure') {
                group.failed += 1;
                continue;  // 失败文件不计入分组进度基数,避免拖低进度。
            }
            var size = Number(file.size_byte) || 0;
            group.total_byte += size;
            if (uploadDone(file)) {
                group.complete += 1;
                group.done_byte += size;
            } else {
                group.done_byte += Math.min(Number(file.completed) || 0, size);  // 上传中的文件按已传字节计入。
            }
        }
        group.percent = group.total_byte ?
            Math.round(group.done_byte / group.total_byte * 1000) / 10 : 0;
        group.stat = groupStat(group.files, {});
    }
    return groups;
}

function uploadSummary(tasks) {
    var total = 0;  // 总量只统计未失败的上传文件,失败文件退出进度基数。
    var done = 0;
    var speed = 0;
    for (var i = 0; i < tasks.length; i++) {
        var file = tasks[i];
        if (file.state === 'failure') {
            continue;  // 失败文件不再计入总量与速度,避免进度被拉低。
        }
        var size = Number(file.size_byte) || 0;
        total += size;
        if (uploadDone(file)) {
            done += size;
        } else if (file.state === 'uploading') {
            done += Math.min(Number(file.completed) || 0, size);  // 上传中的文件按已传字节计入。
        }
        speed += Number(file.speed_value) || 0;
    }
    var remaining = speed && total > done ? (total - done) / speed : null;
    return {
        percent: total ? Math.round(done / total * 1000) / 10 : 0,
        info: sizeText(done) + '/' + sizeText(total),
        speed: speed ? sizeText(speed) + '/s' : '',
        remaining: remaining === null ? '' : secondsText(remaining)
    };
}

function uploadCount(tasks) {
    var count = {success: 0, failure: 0, uploading: 0, pending: 0, active: 0};
    for (var i = 0; i < tasks.length; i++) {
        var state = tasks[i].state;
        if (state === 'failure') {
            count.failure += 1;
        } else if (uploadDone(tasks[i])) {
            count.success += 1;
        } else {
            count.active += 1;
            if (state === 'uploading') {
                count.uploading += 1;
            } else {
                count.pending += 1;
            }
        }
    }
    return count;
}

function uploadRow(file) {
    var state = file.state || 'pending';
    var text = UPLOAD_TEXT[state] || '排队中';
    var cls = UPLOAD_CLASS[state] || 'status-pending';
    var progress;
    if (uploadDone(file)) {
        progress = progressCell(100);
    } else if (state === 'uploading') {
        progress = progressCell(file.percent || 0);
    } else {
        progress = '<span class="cell-progress"><span class="pct' +
            (state === 'pending' ? ' pending' : '') + '">' + text + '</span></span>';
    }
    return '<div class="task-row member-row">' +
        '<span class="cell-name"><span class="ficon">' + (UPLOAD_ICON[state] || '⏳') + '</span>' +
        '<span class="fname" title="' + escAttr(file.path || file.file) + '">' + esc(file.path || file.file) + '</span></span>' +
        progress +
        '<span class="cell-size">' + dash(file.size) + '</span>' +
        '<span class="cell-speed">' + dash(file.speed) + '</span>' +
        '<span class="cell-remain">' + dash(file.remaining) + '</span>' +
        '<span class="cell-status ' + cls + '" title="' + escAttr(file.error) + '">' + text + '</span>' +
        '</div>';
}

function uploadStatusCell(group) {
    if (group.failed) {
        return '<span class="cell-status status-failed">失败 ' + group.failed + ' 个</span>';
    }
    if (group.complete === group.count) {
        return '<span class="cell-status status-done">已完成</span>';
    }
    return '<span class="cell-status status-running">上传中</span>';
}

function uploadBlock(group) {
    var key = 'upload:' + group.channel;
    var isCollapsed = collapsed[key] === undefined ? uploadAllCollapsed : collapsed[key];  // 上传分组默认展开。
    var html = '<div class="group' + (isCollapsed ? '' : ' open') + '" data-channel="' + escAttr(key) + '" data-level="1">' +
        '<div class="group-head" data-channel="' + escAttr(key) + '">' +
        '<span class="cell-name"><span class="arrow"></span>' +
        '<span class="ficon">📺</span>' +
        '<span class="gname" title="' + escAttr(group.name) + '">' + esc(group.name) + '</span>' +
        '<span class="gcount">' + group.count + ' 个文件</span></span>' +
        progressCell(group.percent) +
        '<span class="cell-size">' + group.complete + '/' + group.count + '</span>' +
        groupStatCells(group.stat) +
        uploadStatusCell(group) +
        '</div>' +
        '<div class="group-body"' + (isCollapsed ? ' style="display:none"' : '') + '>';
    for (var i = 0; i < group.files.length; i++) {
        html += uploadRow(group.files[i]);
    }
    return html + '</div></div>';
}

function uploadList(tasks) {
    if (tasks.length === 0) {
        return '<div class="empty">暂无上传任务。</div>';
    }
    var html = '';
    var groups = getUploadGroups(tasks);  // 频道 > 文件完整路径,一级可折叠。
    for (var i = 0; i < groups.length; i++) {
        html += uploadBlock(groups[i]);
    }
    return html;
}

function syncUploadHeads() {
    var list = document.getElementById('upload');
    if (!list || !list.parentNode) {
        return;
    }
    var head = list.parentNode.querySelector('.list-head');
    var level = 1;
    var nodes = list.querySelectorAll('.group.open');
    for (var i = 0; i < nodes.length; i++) {
        if (groupVisible(nodes[i])) {
            level = 2;  // 有任意频道展开时,最内层即为文件行。
            break;
        }
    }
    head.querySelector('.h-name').textContent = UPLOAD_HEAD_NAME[level - 1];
    head.querySelector('.h-size').textContent = UPLOAD_HEAD_SIZE[level - 1];
}

function renderUpload(uploads) {
    var count = uploadCount(uploads);
    document.getElementById('upload').innerHTML = uploadList(uploads);
    document.getElementById('badgeUpload').textContent = count.active;
    syncToggleUpload();
    syncUploadHeads();
    bindGroups();  // 上传列表渲染完成后统一绑定折叠事件。
    renderOverall(uploadSummary(uploads), count.active, SUMMARY_IDS.upload);
    renderStat('uploadStat', [
        statCell('成功', count.success, 'ok'),
        statCell('失败', count.failure, 'bad'),
        statCell('上传中', count.uploading),
        statCell('待上传', count.pending, 'skip'),
        statCell('文件总数', uploads.length, 'queue')
    ]);
    return count.active;
}

function render(data) {
    var downloads = (data.tasks || []).length;
    lastDownloadActive = downloads;
    document.getElementById('badgeDownload').textContent = downloads;
    renderOverall(data.summary, downloads, SUMMARY_IDS.download);
    renderStat('stat', [
        statCell('成功', data.count.success, 'ok'),
        statCell('失败', data.count.failure, 'bad'),
        statCell('跳过', data.count.skip, 'skip'),
        statCell('进行中', downloads),
        statCell('队列中', data.queue || 0, 'queue')
    ]);
    lastUploadActive = renderUpload(data.uploads || []);
    renderStatus();
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

var savedSection = '';
try {
    savedSection = localStorage.getItem(SECTION_KEY) || '';
} catch (e) {
    savedSection = '';
}
bindSections();
switchSection(savedSection);
document.getElementById('toggleAll').onclick = toggleAll;
document.getElementById('toggleUpload').onclick = toggleUploadAll;
refresh();
setInterval(refresh, 1000);
