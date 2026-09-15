const EMPTY_SUMMARY = {percent: 0, info: '0.00B / 0.00B', speed: '', remaining: ''};

var SECTIONS = {
    download: ['download'],
    upload: ['upload'],
    listener: ['listener']
};
var PAGES = SECTIONS.download.concat(SECTIONS.upload, SECTIONS.listener);  // 下载、上传各一个页面,监听页只在内部切换选项卡。
var SUMMARY_IDS = {
    download: {fill: 'overallFill', percent: 'overallPercent', info: 'overallInfo', extra: 'overallExtra'},
    upload: {fill: 'uploadFill', percent: 'uploadPercent', info: 'uploadInfo', extra: 'uploadExtra'}
};  // 下载与上传各自独立的总进度面板,避免相互覆盖。
var SECTION_KEY = 'trmd_section';
var LISTEN_KEY = 'trmd_listen';
var COLLAPSE_KEY = 'trmd_collapsed';  // 各分组折叠状态的本地存储键。
var ALL_KEY = 'trmd_all_collapsed';  // 下载页全部折叠开关的本地存储键。
var UPLOAD_ALL_KEY = 'trmd_upload_all_collapsed';  // 上传页全部折叠开关的本地存储键。
var LINK_LAST_KEY = 'trmd_link_last';  // 下载页链接层最后一次手动选择的本地存储键。
var UPLOAD_LAST_KEY = 'trmd_upload_last';  // 上传页频道层最后一次手动选择的本地存储键。
var LISTEN_TABS = ['forward', 'download'];  // 监听页的选项卡:转发、下载。

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
var lastLinkCollapsed = true;  // 下载页链接层最后的手动选择,缺省折叠以保持原有默认。
var lastUploadCollapsed = false;  // 上传页频道层最后的手动选择,缺省展开以保持原有默认。
var UNGROUPED_NAME = '未分组';
var currentSection = 'download';
var currentListen = 'forward';
var lastDownloadActive = 0;
var lastUploadActive = 0;
var lastListenCount = 0;

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
    var progress;
    if (state === 'success') {
        progress = progressCell(100);
    } else if (item.note) {  // 不支持或被忽略的类型拿不到文件类型,进度栏改为显示具体原因,避免与普通跳过混淆。
        progress = '<span class="cell-progress"><span class="pct note" title="' + escAttr(item.note) + '">' +
            esc(item.note) + '</span></span>';
    } else {
        progress = '<span class="cell-progress"><span class="pct' + (pending ? ' pending' : '') + '">' + text + '</span></span>';
    }
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
        var base = channelGroup.member - channelGroup.failed;  // 彻底失败的成员退出进度基数,避免进度永远到不了100%。
        channelGroup.percent = base ?
            Math.round(channelGroup.complete / base * 1000) / 10 : 0;
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
    var isCollapsed = collapsed[key] === undefined ? lastLinkCollapsed : collapsed[key];  // 无记录的链接沿用上次的链接层选择。
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
    document.getElementById('headName').querySelector('.htext').textContent = HEAD_LABELS[level - 1];
    document.getElementById('headSize').querySelector('.htext').textContent = SIZE_LABELS[level - 1];  // 分组行是条数,成员行才是字节。
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
            saveState(COLLAPSE_KEY, JSON.stringify(collapsed));  // 记住本次折叠,刷新后恢复。
            if (group.getAttribute('data-level') === '2') {
                lastLinkCollapsed = hide;  // 下载页链接层的手动选择。
                saveState(LINK_LAST_KEY, hide ? '1' : '0');
            } else if (group.closest('#upload')) {
                lastUploadCollapsed = hide;  // 上传页频道层的手动选择。
                saveState(UPLOAD_LAST_KEY, hide ? '1' : '0');
            }
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
    saveState(COLLAPSE_KEY, JSON.stringify(collapsed));  // 批量折叠后同样落盘,刷新后保持。
    if (selector === '#download') {
        lastLinkCollapsed = hide;  // 批量操作同样视为一次链接层选择。
        saveState(LINK_LAST_KEY, hide ? '1' : '0');
    } else {
        lastUploadCollapsed = hide;  // 批量操作同样视为一次频道层选择。
        saveState(UPLOAD_LAST_KEY, hide ? '1' : '0');
    }
}

function toggleAll() {
    allCollapsed = !allCollapsed;
    saveState(ALL_KEY, allCollapsed ? '1' : '0');
    setAllGroups('#download', allCollapsed);
    syncToggleAll();
    syncHeadLabel();
}

function toggleUploadAll() {
    uploadAllCollapsed = !uploadAllCollapsed;
    saveState(UPLOAD_ALL_KEY, uploadAllCollapsed ? '1' : '0');
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

function applyListenTab() {
    var tabs = document.querySelectorAll('#listenTabs .tab');
    for (var i = 0; i < tabs.length; i++) {
        var active = tabs[i].getAttribute('data-listen') === currentListen;
        tabs[i].className = active ? 'tab active' : 'tab';
    }
    document.getElementById('listenForwardBox').hidden = currentListen !== 'forward';
    document.getElementById('listenDownloadBox').hidden = currentListen !== 'download';
}

function switchListen(name) {
    if (LISTEN_TABS.indexOf(name) === -1) {
        name = LISTEN_TABS[0];
    }
    currentListen = name;
    applyListenTab();
    saveState(LISTEN_KEY, currentListen);
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
    // 下载、上传、监听三个板块的活跃情况统一显示在顶栏左侧,不再跟随当前板块切换。
    var parts = [];
    if (lastDownloadActive) {
        parts.push('下载 ' + lastDownloadActive);
    }
    if (lastUploadActive) {
        parts.push('上传 ' + lastUploadActive);
    }
    if (lastListenCount) {
        parts.push('监听 ' + lastListenCount);
    }
    var active = parts.length > 0;
    document.getElementById('dot').className = active ? 'dot active' : 'dot';
    document.getElementById('statusText').textContent = active ? parts.join(' · ') : '空闲 · 等待任务';
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

function listenRow(kind, source, target) {
    var link = target ? source + ' ' + target : source;  // 与后端监听字典的键保持一致。
    var html = '<div class="task-row">' +
        '<span class="cell-name"><span class="ficon">🕵️</span>' +
        '<span class="fname" title="' + escAttr(source) + '">' + esc(source) + '</span></span>';
    if (target) {
        html += '<span class="cell-name"><span class="ficon">➡️</span>' +
            '<span class="fname" title="' + escAttr(target) + '">' + esc(target) + '</span></span>';
    }
    html += '<span class="cell-action"><button class="btn-del" type="button" title="移除该监听"' +
        ' data-kind="' + kind + '" data-link="' + escAttr(link) + '">✖</button></span>';
    return html + '</div>';
}

function renderListeners(listeners) {
    var data = listeners || {};
    var forward = data.forward || [];
    var download = data.download || [];
    var html = '';
    var i;
    for (i = 0; i < forward.length; i++) {
        html += listenRow('forward', forward[i].source, forward[i].target);
    }
    document.getElementById('listenForward').innerHTML = html ? html : '<div class="empty">暂无监听转发。</div>';
    html = '';
    for (i = 0; i < download.length; i++) {
        html += listenRow('download', download[i]);
    }
    document.getElementById('listenDownload').innerHTML = html ? html : '<div class="empty">暂无监听下载。</div>';
    return forward.length + download.length;
}

async function removeListener(kind, link) {
    if (!link) {
        return;
    }
    try {
        var res = await fetch('/api/listener/remove', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({kind: kind, link: link})
        });
        var data = await res.json();
        if (!data.status) {
            window.alert('移除失败:' + (data.e_code || '未知错误。'));
        }
    } catch (e) {
        window.alert('移除失败:无法连接程序。');
    }
    refresh();  // 移除后立即刷新,无需等待下一次轮询。
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
    var isCollapsed = collapsed[key] === undefined ? lastUploadCollapsed : collapsed[key];  // 无记录的上传分组沿用上次的频道层选择。
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
    head.querySelector('.h-name .htext').textContent = UPLOAD_HEAD_NAME[level - 1];
    head.querySelector('.h-size .htext').textContent = UPLOAD_HEAD_SIZE[level - 1];
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
    lastListenCount = renderListeners(data.listeners);
    renderOuterLinks(data.outer_links);
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

function bindListenTabs() {
    var tabs = document.querySelectorAll('#listenTabs .tab');
    for (var i = 0; i < tabs.length; i++) {
        tabs[i].onclick = function () {
            switchListen(this.getAttribute('data-listen'));
        };
    }
}

function bindListenRemove() {
    var box = document.getElementById('page-listener');  // 用事件委托,避免每次轮询重新绑定。
    box.onclick = function (event) {
        var target = event.target;
        if (!target || !target.classList || !target.classList.contains('btn-del')) {
            return;
        }
        removeListener(target.getAttribute('data-kind'), target.getAttribute('data-link'));
    };
}

function openSupport() {
    document.getElementById('supportModal').hidden = false;
}

function closeSupport() {
    document.getElementById('supportModal').hidden = true;
}

function supportMaskClick(event) {
    if (event.target === this) {  // 点击遮罩空白处关闭弹窗。
        closeSupport();
    }
}

function supportEscape(event) {
    if (event.key === 'Escape' && !document.getElementById('supportModal').hidden) {
        closeSupport();
    }
}

var OUTER_LINK_IDS = {github: 'linkGithub', subscribe_channel: 'linkChannel', video_tutorial: 'linkVideo'};

function renderOuterLinks(links) {
    Object.keys(OUTER_LINK_IDS).forEach(function (key) {
        var node = document.getElementById(OUTER_LINK_IDS[key]);
        var url = (links || {})[key];
        node.href = url || '#';
        node.hidden = !url;  // 后端未提供该链接时隐藏对应菜单项。
    });
}

function setMenuOpen(open) {
    document.getElementById('menuDropdown').hidden = !open;
}

function menuBtnClick(event) {
    event.stopPropagation();  // 阻止冒泡,避免立刻被外部点击处理关闭。
    setMenuOpen(document.getElementById('menuDropdown').hidden);
}

function menuOutsideClick(event) {
    if (!document.getElementById('menuWrap').contains(event.target)) {
        setMenuOpen(false);
    }
}

function menuEscape(event) {
    if (event.key === 'Escape') {
        setMenuOpen(false);
    }
}

function bindMenu() {
    document.getElementById('menuBtn').onclick = menuBtnClick;
    document.addEventListener('click', menuOutsideClick);
    document.addEventListener('keydown', menuEscape);
}

function isFirstLogin() {
    return document.body.getAttribute('data-first-login') === '1';  // 服务端在首次登录时写入该标记。
}

function bindSupport() {
    document.getElementById('supportBtn').onclick = openSupport;
    document.getElementById('supportClose').onclick = closeSupport;
    document.getElementById('supportModal').onclick = supportMaskClick;
    document.addEventListener('keydown', supportEscape);
    if (isFirstLogin()) {
        openSupport();
    }
}

var COLS_KEY = 'trmd_cols';  // 各表列宽的本地存储键。
var COLS_MIN = 48;  // 单列最小宽度,避免被拖到不可读。
var colsCache = {};  // 表名 -> 非弹性列的像素宽度数组。
var dragState = null;  // 拖拽过程中的临时状态。

function readDefaultCols(list) {
    var text = window.getComputedStyle(list).getPropertyValue('--cols');  // 自定义属性在隐藏元素上也可读取。
    var matches = text.match(/(\d+(?:\.\d+)?)px/g) || [];
    var widths = [];
    for (var i = 0; i < matches.length; i++) {
        widths.push(Math.round(parseFloat(matches[i])));
    }
    return widths.length ? widths : [COLS_MIN];
}

function applyCols(list, widths) {
    var parts = ['minmax(0, 1fr)'];  // 首列始终弹性,自适应剩余宽度。
    for (var i = 0; i < widths.length; i++) {
        parts.push(widths[i] + 'px');
    }
    list.style.setProperty('--cols', parts.join(' '));
}

function buildGrips(list) {
    var head = list.querySelector('.list-head');
    var cells = head.children;
    var table = list.getAttribute('data-table');
    for (var i = 0; i < cells.length - 1; i++) {  // 末列格右侧为容器边界,不生成分隔条。
        if (cells[i].querySelector('.grip')) {
            continue;  // 已存在分隔条时不重复创建。
        }
        var grip = document.createElement('span');
        grip.className = 'grip';
        grip.setAttribute('data-table', table);
        grip.setAttribute('data-index', i);
        grip.onpointerdown = resizeStart;
        cells[i].appendChild(grip);
    }
}

function clampColsWidth(widths, index, value, maxFixed) {
    var others = 0;
    for (var i = 0; i < widths.length; i++) {
        if (i !== index) {
            others += widths[i];
        }
    }
    var max = Math.max(COLS_MIN, maxFixed - others);
    return Math.min(Math.max(value, COLS_MIN), max);
}

function resizeStart(event) {
    var grip = event.currentTarget;
    var list = grip.closest('.list');
    var head = list.querySelector('.list-head');
    var index = Number(grip.getAttribute('data-index'));
    var table = list.getAttribute('data-table');
    var widths = colsCache[table] || readDefaultCols(list);
    var style = window.getComputedStyle(head);
    var gap = parseFloat(style.columnGap) || 0;
    var padding = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
    dragState = {
        list: list,
        table: table,
        index: index,
        col: index === 0 ? 0 : index - 1,  // 分隔条所属列格对应的固定列下标。
        sign: index === 0 ? -1 : 1,  // 首个分隔条调整右侧列,其余调整左侧列。
        origin: widths.slice(),
        widths: widths.slice(),
        startX: event.clientX,
        maxFixed: Math.max(head.clientWidth - padding - gap * widths.length, 0)
    };
    event.preventDefault();
    event.stopPropagation();
    document.body.classList.add('resizing');
    document.addEventListener('pointermove', resizeMove);
    document.addEventListener('pointerup', resizeEnd);
}

function resizeMove(event) {
    if (!dragState) {
        return;
    }
    var delta = event.clientX - dragState.startX;
    var value = dragState.origin[dragState.col] + delta * dragState.sign;
    dragState.widths[dragState.col] = clampColsWidth(dragState.widths, dragState.col, value, dragState.maxFixed);
    applyCols(dragState.list, dragState.widths);
    event.preventDefault();
}

function resizeEnd() {
    if (!dragState) {
        return;
    }
    colsCache[dragState.table] = dragState.widths;
    try {
        localStorage.setItem(COLS_KEY, JSON.stringify(colsCache));  // 记住本次列宽,刷新后恢复。
    } catch (e) {
        // 隐私模式下写入失败可忽略。
    }
    document.body.classList.remove('resizing');
    document.removeEventListener('pointermove', resizeMove);
    document.removeEventListener('pointerup', resizeEnd);
    dragState = null;
}

function initCols() {
    try {
        colsCache = JSON.parse(localStorage.getItem(COLS_KEY) || '{}') || {};
    } catch (e) {
        colsCache = {};
    }
    var lists = document.querySelectorAll('.list[data-table]');
    for (var i = 0; i < lists.length; i++) {
        var list = lists[i];
        var table = list.getAttribute('data-table');
        var head = list.querySelector('.list-head');
        var widths = colsCache[table];
        if (!widths || widths.length !== head.children.length - 1) {
            widths = readDefaultCols(list);  // 列数变化或首次加载时回退到默认列宽。
        }
        colsCache[table] = widths;
        applyCols(list, widths);
        buildGrips(list);
    }
}

var savedSection = '';
var savedListen = '';
try {
    savedSection = localStorage.getItem(SECTION_KEY) || '';
    savedListen = localStorage.getItem(LISTEN_KEY) || '';
    collapsed = JSON.parse(localStorage.getItem(COLLAPSE_KEY) || '{}') || {};  // 读回各分组折叠状态。
    allCollapsed = localStorage.getItem(ALL_KEY) === '1';
    uploadAllCollapsed = localStorage.getItem(UPLOAD_ALL_KEY) === '1';
    lastLinkCollapsed = localStorage.getItem(LINK_LAST_KEY) !== '0';  // 无记录时保持链接层默认折叠。
    lastUploadCollapsed = localStorage.getItem(UPLOAD_LAST_KEY) === '1';  // 无记录时保持上传频道层默认展开。
} catch (e) {
    savedSection = '';
    savedListen = '';
    collapsed = {};
    allCollapsed = false;
    uploadAllCollapsed = false;
    lastLinkCollapsed = true;
    lastUploadCollapsed = false;
}
function initVersion() {
    var tip = document.getElementById('logoVersion');
    var trmd = document.getElementById('tipTrmd');
    var pyrogram = document.getElementById('tipPyrogram');
    if (trmd.textContent.indexOf('__') === 0 || pyrogram.textContent.indexOf('__') === 0) {
        tip.hidden = true;  // 占位符未被服务端替换时隐藏,避免显示原始占位文本。
    }
}

/* ===== 动画渐变背景,逐行移植自 Telegram Web K 的 gradientRenderer.ts ===== */
var BG_GRADIENT_SIZE = 50;  // 画布分辨率,与 Telegram Web 一致,靠 CSS 拉伸获得柔和观感。
var BG_GRADIENT_TAILS = 90;  // 相邻两个色点位置之间的过渡帧数,数值越大漂移越慢。
var BG_GRADIENT_FPS = 15;  // 动画帧率上限,与原版脚本一致,开销极低且足够平滑。
var BG_GRADIENT_POSITIONS = [  // 8 个色点的归一化坐标,渲染时按相位轮换参与,与原版一致。
    {x: 0.80, y: 0.10},
    {x: 0.60, y: 0.20},
    {x: 0.35, y: 0.25},
    {x: 0.25, y: 0.60},
    {x: 0.20, y: 0.90},
    {x: 0.40, y: 0.80},
    {x: 0.65, y: 0.75},
    {x: 0.75, y: 0.40}
];
var bgCanvas = null;
var bgCtx = null;
var bgHelperCanvas = null;  // 隐藏的 50×50 画布,先写入 ImageData 再拷贝到主画布,与原版一致。
var bgHelperCtx = null;
var bgColors = [];
var bgPhase = 0;
var bgTail = 0;
var bgLastFrame = 0;

function bgHexToRgb(hex) {  // 把 #rrggbb 颜色解析为 [r, g, b] 数组。
    var value = parseInt(hex.slice(1, 7), 16);
    return [(value >> 16) & 255, (value >> 8) & 255, value & 255];
}

function bgGetPositions(shift) {  // 把色点数组按 shift 旋转后隔一取一,得到本相位参与渲染的 4 个点。
    var positions = BG_GRADIENT_POSITIONS.slice();
    positions.push.apply(positions, positions.splice(0, shift));
    var result = [];
    for (var i = 0; i < positions.length; i += 2) {
        result.push(positions[i]);
    }
    return result;
}

function bgPositionsForPhase(phase) {  // 取某相位渲染用的 4 个色点,Y 轴翻转与原版一致。
    var result = [];
    for (var i = 0; i != 4; ++i) {
        var point = BG_GRADIENT_POSITIONS[(phase + i * 2) % BG_GRADIENT_POSITIONS.length];
        result.push({x: point.x, y: 1.0 - point.y});
    }
    return result;
}

function bgGetGradientImageData(phase, tail) {  // 按 Telegram 的漩涡算法逐像素混合 4 个色点颜色,生成 ImageData。
    var id = bgHelperCtx.createImageData(BG_GRADIENT_SIZE, BG_GRADIENT_SIZE);
    var pixels = id.data;
    var colorsLength = bgColors.length;
    var previous = bgPositionsForPhase((phase + 1) % BG_GRADIENT_POSITIONS.length);
    var current = bgPositionsForPhase(phase);
    var progress = 1 - tail / BG_GRADIENT_TAILS;
    var offset = 0;
    for (var y = 0; y < BG_GRADIENT_SIZE; ++y) {
        var directPixelY = y / BG_GRADIENT_SIZE;
        var centerDistanceY = directPixelY - 0.5;
        var centerDistanceY2 = centerDistanceY * centerDistanceY;
        for (var x = 0; x < BG_GRADIENT_SIZE; ++x) {
            var directPixelX = x / BG_GRADIENT_SIZE;
            var centerDistanceX = directPixelX - 0.5;
            var centerDistance = Math.sqrt(centerDistanceX * centerDistanceX + centerDistanceY2);
            var swirlFactor = 0.35 * centerDistance;
            var theta = swirlFactor * swirlFactor * 0.8 * 8.0;
            var sinTheta = Math.sin(theta);
            var cosTheta = Math.cos(theta);
            var pixelX = Math.max(0.0, Math.min(1.0, 0.5 + centerDistanceX * cosTheta - centerDistanceY * sinTheta));
            var pixelY = Math.max(0.0, Math.min(1.0, 0.5 + centerDistanceX * sinTheta + centerDistanceY * cosTheta));
            var distanceSum = 0.0;
            var r = 0.0;
            var g = 0.0;
            var b = 0.0;
            for (var i = 0; i < colorsLength; ++i) {
                var colorX = previous[i].x + (current[i].x - previous[i].x) * progress;
                var colorY = previous[i].y + (current[i].y - previous[i].y) * progress;
                var distanceX = pixelX - colorX;
                var distanceY = pixelY - colorY;
                var distance = Math.max(0.0, 0.9 - Math.sqrt(distanceX * distanceX + distanceY * distanceY));
                distance = distance * distance * distance * distance;
                distanceSum += distance;
                r += distance * bgColors[i][0];
                g += distance * bgColors[i][1];
                b += distance * bgColors[i][2];
            }
            pixels[offset++] = r / distanceSum;
            pixels[offset++] = g / distanceSum;
            pixels[offset++] = b / distanceSum;
            pixels[offset++] = 0xFF;
        }
    }
    return id;
}

function bgDrawImageData(id) {  // 先写入隐藏画布再拷贝到主画布,与原版的 hc/hctx 两级结构一致。
    bgHelperCtx.putImageData(id, 0, 0);
    bgCtx.drawImage(bgHelperCanvas, 0, 0, BG_GRADIENT_SIZE, BG_GRADIENT_SIZE);
}

function bgChangeTail(diff) {  // 推进过渡进度,跨越尾数时切换相位,与原版 changeTail 一致。
    bgTail += diff;
    while (bgTail >= BG_GRADIENT_TAILS) {
        bgTail -= BG_GRADIENT_TAILS;
        if (++bgPhase >= BG_GRADIENT_POSITIONS.length) {
            bgPhase -= BG_GRADIENT_POSITIONS.length;
        }
    }
    while (bgTail < 0) {
        bgTail += BG_GRADIENT_TAILS;
        if (--bgPhase < 0) {
            bgPhase += BG_GRADIENT_POSITIONS.length;
        }
    }
}

function bgAnimateLoop(now) {  // 持续漂移动画:每帧推进一格尾数,带焦点检测与帧率限制,与原版 doAnimate 一致。
    requestAnimationFrame(bgAnimateLoop);
    if (!document.hasFocus() || (now - bgLastFrame) < 1000 / BG_GRADIENT_FPS) {
        return;
    }
    bgLastFrame = now;
    bgChangeTail(1);
    bgDrawImageData(bgGetGradientImageData(bgPhase, bgTail));
}

function initBackgroundGradient() {
    bgCanvas = document.getElementById('bgGradient');
    if (!bgCanvas || !bgCanvas.getContext) {
        return;
    }
    bgHelperCanvas = document.createElement('canvas');
    bgHelperCanvas.width = BG_GRADIENT_SIZE;
    bgHelperCanvas.height = BG_GRADIENT_SIZE;
    bgHelperCtx = bgHelperCanvas.getContext('2d', {alpha: false});
    var colors = (bgCanvas.getAttribute('data-colors') || '').split(',');
    for (var i = 0; i < colors.length; i++) {
        var color = colors[i].trim();
        if (/^#[0-9a-fA-F]{6}$/.test(color)) {
            bgColors.push(bgHexToRgb(color));
        }
    }
    if (!bgColors.length) {
        return;
    }
    bgCtx = bgCanvas.getContext('2d', {alpha: false});
    bgDrawImageData(bgGetGradientImageData(0, 0));  // 先绘制一帧静态渐变,避免脚本异常时背景空白。
    bgCanvas.classList.add('on');
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;  // 用户偏好减少动效时只保留静态渐变。
    }
    requestAnimationFrame(bgAnimateLoop);
}

bindSections();
bindListenTabs();
bindListenRemove();
bindSupport();
bindMenu();
initVersion();
switchSection(savedSection);
switchListen(savedListen);
document.getElementById('toggleAll').onclick = toggleAll;
document.getElementById('toggleUpload').onclick = toggleUploadAll;
initCols();  // 恢复上次的列宽并生成拖拽分隔条。
initBackgroundGradient();  // 启动 Telegram 风格的动画渐变背景。
refresh();
setInterval(refresh, 1000);
