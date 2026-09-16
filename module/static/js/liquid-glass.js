/* 液态玻璃(Liquid Glass)效果实现。
 * 移植自 liquid-glass 项目:
 * MIT license Copyright (c) 2025 Nikita Stadnik <https://github.com/nikdelvin/liquid-glass>,
 * 将 SVG 位移贴图(displacement map)注入 backdrop-filter,
 * 让卡片边缘产生折射般的玻璃厚度感,而非普通毛玻璃的均匀模糊。
 * 实现方式:在 DOM 中维护内联 <svg> 滤镜,卡片通过 backdrop-filter: url(#id) 引用,
 * 该方式在 Chromium 内核浏览器中可靠生效(比整段滤镜塞进 data URI 更稳定)。 */

// 生成位移贴图:一张用于驱动 feDisplacementMap 的 RGB 渐变图,边缘形成玻璃斜面。
function lgGetDisplacementMap(opts) {
    const { height, width, radius, depth } = opts;
    const safeRadius = isFinite(radius) ? radius : 0;
    const svg =
        '<svg height="' + height + '" width="' + width + '" viewBox="0 0 ' + width + ' ' + height + '" xmlns="http://www.w3.org/2000/svg">' +
        '<style>.mix { mix-blend-mode: screen; }</style>' +
        '<defs>' +
        '<linearGradient id="Y" x1="0" x2="0" y1="' + Math.ceil((safeRadius / height) * 15) + '%" y2="' + Math.floor(100 - (safeRadius / height) * 15) + '%">' +
        '<stop offset="0%" stop-color="#0F0" /><stop offset="100%" stop-color="#000" />' +
        '</linearGradient>' +
        '<linearGradient id="X" x1="' + Math.ceil((safeRadius / width) * 15) + '%" x2="' + Math.floor(100 - (safeRadius / width) * 15) + '%" y1="0" y2="0">' +
        '<stop offset="0%" stop-color="#F00" /><stop offset="100%" stop-color="#000" />' +
        '</linearGradient>' +
        '</defs>' +
        '<rect x="0" y="0" height="' + height + '" width="' + width + '" fill="#808080" />' +
        '<g filter="blur(2px)">' +
        '<rect x="0" y="0" height="' + height + '" width="' + width + '" fill="#000080" />' +
        '<rect x="0" y="0" height="' + height + '" width="' + width + '" fill="url(#Y)" class="mix" />' +
        '<rect x="0" y="0" height="' + height + '" width="' + width + '" fill="url(#X)" class="mix" />' +
        '<rect x="' + depth + '" y="' + depth + '" height="' + (height - 2 * depth) + '" width="' + (width - 2 * depth) + '" fill="#808080" rx="' + safeRadius + '" ry="' + safeRadius + '" filter="blur(' + depth + 'px)" />' +
        '</g>' +
        '</svg>';
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
}

// 生成滤镜内部 SVG:以位移贴图驱动 feDisplacementMap 扭曲背景,并按通道做色散增强折射感。
function lgGetFilterInner(opts) {
    const { height, width, radius, depth, strength = 100, chromaticAberration = 0 } = opts;
    const map = lgGetDisplacementMap({ height, width, radius, depth });
    return '<feImage x="0" y="0" height="' + height + '" width="' + width + '" href="' + map + '" result="displacementMap" />' +
        '<feDisplacementMap in="SourceGraphic" in2="displacementMap" scale="' + (strength + chromaticAberration * 2) + '" xChannelSelector="R" yChannelSelector="G" />' +
        '<feColorMatrix type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" result="displacedR" />' +
        '<feDisplacementMap in="SourceGraphic" in2="displacementMap" scale="' + (strength + chromaticAberration) + '" xChannelSelector="R" yChannelSelector="G" />' +
        '<feColorMatrix type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0" result="displacedG" />' +
        '<feDisplacementMap in="SourceGraphic" in2="displacementMap" scale="' + strength + '" xChannelSelector="R" yChannelSelector="G" />' +
        '<feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0" result="displacedB" />' +
        '<feBlend in="displacedR" in2="displacedG" mode="screen" />' +
        '<feBlend in2="displacedB" mode="screen" />';
}

// 检测浏览器是否支持 backdrop-filter: url(#...)。
const lgSupportsUrl = (function () {
    const el = document.createElement('div');
    el.style.cssText = 'backdrop-filter: url(#test)';
    return el.style.backdropFilter === 'url(#test)' || el.style.backdropFilter === 'url("#test")';
})();

// 获取/创建内联滤镜容器,所有滤镜都挂在这里,供卡片以 url(#id) 引用。
function lgGetDefs() {
    let svg = document.getElementById('lg-svg');
    if (!svg) {
        svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.id = 'lg-svg';
        svg.setAttribute('style', 'position:absolute;width:0;height:0;overflow:hidden;pointer-events:none;');
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        svg.appendChild(defs);
        document.body.appendChild(svg);
    }
    return svg.querySelector('defs');
}

// 元素 -> 滤镜 id 的映射,避免重复创建。
const lgMap = new WeakMap();
let lgSeq = 0;

// 根据元素尺寸与边框圆角,重算并应用液态玻璃的背景滤镜。
function lgRedraw(glass) {
    const rect = glass.getBoundingClientRect();
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height));
    const cs = getComputedStyle(glass);
    // 圆角限制在短边一半以内,避免胶囊形卡片折射过强。
    const radius = Math.min(parseFloat(cs.borderRadius) || 0, Math.min(width, height) / 2);
    const blur = parseFloat(glass.dataset.lgBlur || '2');
    const depth = parseFloat(glass.dataset.lgDepth || '4');
    const strength = parseFloat(glass.dataset.lgStrength || '140');
    const cab = parseFloat(glass.dataset.lgCab || '0');
    const saturate = parseFloat(glass.dataset.lgSaturate || '1.9');
    const brightness = parseFloat(glass.dataset.lgBrightness || '1');
    const bf =
        'blur(' + (blur / 2) + 'px) saturate(' + saturate + ') brightness(' + brightness + ')';

    if (!lgSupportsUrl) {
        // 不支持时回退为普通毛玻璃,保留上沿高光与淡投影以维持质感。
        glass.style.backdropFilter = bf;
        glass.style.webkitBackdropFilter = bf;
        glass.style.boxShadow = 'inset 0 1px 0 rgba(255, 255, 255, .06), 0 4px 16px rgba(0, 0, 0, .28)';
        return;
    }

    // 为元素分配并重建专属滤镜。
    let id = lgMap.get(glass);
    if (!id) {
        id = 'lg-glass-' + (++lgSeq);
        lgMap.set(glass, id);
    }
    const defs = lgGetDefs();
    let filter = document.getElementById(id);
    if (filter) {
        filter.remove();
    }
    filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
    filter.id = id;
    filter.setAttribute('color-interpolation-filters', 'sRGB');
    // 扩张滤镜区域,避免边缘折射被裁切。
    filter.setAttribute('x', '-20%');
    filter.setAttribute('y', '-20%');
    filter.setAttribute('width', '140%');
    filter.setAttribute('height', '140%');
    filter.innerHTML = lgGetFilterInner({ height, width, radius, depth, strength, chromaticAberration: cab });
    defs.appendChild(filter);

    const value = 'blur(' + (blur / 2) + 'px) url(#' + id + ') ' + bf;
    glass.style.backdropFilter = value;
    glass.style.webkitBackdropFilter = value;
}

// 为单个元素应用效果并监听尺寸变化。
function lgBind(glass) {
    lgRedraw(glass);
    const ro = new ResizeObserver(function () {
        lgRedraw(glass);
    });
    ro.observe(glass);
}

// 仅对未绑定过的元素执行绑定,用于 MutationObserver 回调中避免重复。
function lgBindIfNew(el) {
    if (!el.dataset.lgBound) {
        el.dataset.lgBound = '1';
        lgBind(el);
    }
}

// 初始化:对静态卡片直接应用,对动态生成的元素用 MutationObserver 追加。
function lgInit() {
    // 侧边栏、总进度面板、监听选项卡、可折叠任务列表、表头各列标题均为静态元素,直接绑定。
    const direct = document.querySelectorAll('.side-item, .panel, .tab, .list, .group-head, .list-head > span:not(.grip)');
    direct.forEach(lgBind);

    // 统计状态卡(.stat div)由脚本动态生成,统一通过容器监听追加,避免重复绑定。
    document.querySelectorAll('.stat').forEach(function (container) {
        container.querySelectorAll('.stat div').forEach(lgBindIfNew);
        const mo = new MutationObserver(function () {
            container.querySelectorAll('.stat div').forEach(lgBindIfNew);
        });
        mo.observe(container, { childList: true });
    });

    // 可折叠任务列表内的分组标题(.group-head)为动态生成,监听列表变化追加效果。
    document.querySelectorAll('.list').forEach(function (list) {
        list.querySelectorAll('.group-head').forEach(lgBindIfNew);
        const mo = new MutationObserver(function () {
            list.querySelectorAll('.group-head').forEach(lgBindIfNew);
        });
        mo.observe(list, { childList: true, subtree: true });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', lgInit);
} else {
    lgInit();
}
