/** Page FB ↔ Google Sheet bridge (one-time install). */
const PAGE_FB_SYNC_TAB = 'Page FB Sync';
const PAGE_FB_PRESENTATION_TAB = 'Trang tính2';
const PAGE_FB_AUTO_MARKER = 'PAGE FB — CẬP NHẬT TỰ ĐỘNG';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('Page FB')
    .addItem('Đồng bộ Sheet → tool', 'requestToolSync')
    .addItem('Đánh dấu kiểm tra view', 'requestViewCheck')
    .addSeparator()
    .addItem('Cập nhật Trang tính2', 'updatePresentationTab')
    .addToUi();
  ensureSyncTab_();
}
function onEdit(e) {
  const r = e && e.range;
  if (!r || r.getSheet().getName() !== PAGE_FB_SYNC_TAB || r.getColumn() !== 4 || r.getValue() !== true) return;
  if (r.getRow() === 2) requestToolSync();
  if (r.getRow() === 3) requestViewCheck();
  if (r.getRow() === 6) updatePresentationTab();
  r.setValue(false);
}
function ensureSyncTab_() {
  const ss = SpreadsheetApp.getActive();
  let sh = ss.getSheetByName(PAGE_FB_SYNC_TAB);
  if (!sh) sh = ss.insertSheet(PAGE_FB_SYNC_TAB);
  if (!sh.getRange('A1').getValue()) sh.getRange('A1:B5').setValues([
    ['Page FB Sync', 'Giá trị'], ['Lệnh', ''], ['Kiểm tra view', ''],
    ['Hướng dẫn', 'Bấm menu Page FB hoặc ô chọn tương ứng.'], ['Trạng thái', 'Chờ tool xử lý']
  ]);
  sh.getRange('A6:C6').setValues([['Cập nhật Trang tính2', '', 'Tích ô D6 để cập nhật theo Page FB Sync']]);
  sh.getRange('D2:D3').insertCheckboxes();
  sh.getRange('D6').insertCheckboxes();
  sh.autoResizeColumns(1, 4);
  return sh;
}
function requestToolSync() {
  const sh = ensureSyncTab_();
  sh.getRange('B2:B3').setValues([['sync_from_sheet'], [new Date()]]);
  sh.getRange('B5').setValue('Đã đánh dấu yêu cầu. Tải vùng A7:J1000 rồi bấm Đồng bộ từ Sheet trên tool.');
}
function requestViewCheck() {
  const sh = ensureSyncTab_();
  sh.getRange('B2:B3').setValues([['check_views'], [new Date()]]);
  sh.getRange('B5').setValue('Đã đánh dấu yêu cầu kiểm tra view. Bấm Kiểm tra view Page trên tool.');
}
function _s_(v) { return String(v == null ? '' : v).trim(); }
function _status_(v) { const s = _s_(v).toLowerCase(); return s === 'red' || s === 'đỏ' ? 'Đỏ' : s === 'green' || s === 'xanh' ? 'Xanh' : 'Hoạt động'; }
function _color_(v) { const s = _status_(v); return s === 'Đỏ' ? '#ff0000' : s === 'Xanh' ? '#00ff00' : '#ffff00'; }
function _linkFormula_(v) { const u = _s_(v).replace(/"/g, '""'); return u ? '=HYPERLINK("' + u + '";"Mở Reel")' : ''; }
function _groups_() {
  const sh = SpreadsheetApp.getActive().getSheetByName(PAGE_FB_SYNC_TAB);
  if (!sh || sh.getLastRow() < 8) return [];
  const rows = sh.getRange(8, 1, sh.getLastRow() - 7, 10).getDisplayValues();
  const out = {};
  rows.forEach(function(r) {
    const account = _s_(r[9]) || 'Tài khoản', group = _s_(r[0]) || 'Không có cụm', proxy = _s_(r[1]) || 'Không có proxy';
    const key = account + '\u0001' + group + '\u0001' + proxy;
    if (!out[key]) out[key] = {account: account, group: group, proxy: proxy, pages: []};
    out[key].pages.push({name: _s_(r[2]), id: _s_(r[3]), status: _status_(r[4]), link: _s_(r[5]), r1: _s_(r[6]), r2: _s_(r[7]), r3: _s_(r[8])});
  });
  return Object.keys(out).map(function(k) { return out[k]; });
}
function _startRow_(sh) {
  const values = sh.getRange(1, 1, Math.max(sh.getLastRow(), 1), 1).getDisplayValues();
  for (let i = 0; i < values.length; i++) if (_s_(values[i][0]).indexOf(PAGE_FB_AUTO_MARKER) === 0 || /^Tài khoản .* — .* Page$/i.test(_s_(values[i][0]))) return i + 1;
  return sh.getLastRow() + 2;
}
function _block_(sh, row, col, g) {
  sh.getRange(row, col, 1, 8).merge().setValue(g.account + ' — ' + g.group + ' — Proxy ' + g.proxy + ' — ' + g.pages.length + ' Page').setBackground('#17365d').setFontColor('#fff').setFontWeight('bold').setHorizontalAlignment('center');
  sh.getRange(row + 1, col, 1, 8).setValues([['STT','Tên Page Facebook','Link Reel','Tình trạng','Facebook ID','Reel 1','Reel 2','Reel 3']]).setBackground('#1f4e78').setFontColor('#fff').setFontWeight('bold').setHorizontalAlignment('center');
  const values = g.pages.map(function(p, i) { return [i + 1, p.name, '', p.status, p.id, p.r1, p.r2, p.r3]; });
  if (!values.length) return row + 2;
  sh.getRange(row + 2, col, values.length, 8).setValues(values).setBorder(true, true, true, true, true, true, '#b7b7b7', SpreadsheetApp.BorderStyle.SOLID);
  sh.getRange(row + 2, col + 2, values.length, 1).setFormulas(g.pages.map(function(p) { return [_linkFormula_(p.link)]; })).setFontColor('#0563c1').setFontLine('underline');
  g.pages.forEach(function(p, i) { sh.getRange(row + 2 + i, col + 3).setBackground(_color_(p.status)); });
  return row + 2 + values.length;
}
function updatePresentationTab() {
  const ss = SpreadsheetApp.getActive(), sync = ensureSyncTab_(), groups = _groups_();
  if (!groups.length) { sync.getRange('B5').setValue('Chưa có dữ liệu Page FB Sync từ dòng 8.'); return; }
  let sh = ss.getSheetByName(PAGE_FB_PRESENTATION_TAB); if (!sh) sh = ss.insertSheet(PAGE_FB_PRESENTATION_TAB);
  const start = _startRow_(sh);
  sh.getRange(start, 1, Math.max(sh.getMaxRows() - start + 1, 1), sh.getMaxColumns()).breakApart().clear({contentsOnly: false});
  sh.getRange(start, 1, 1, 17).merge().setValue(PAGE_FB_AUTO_MARKER + ' — ' + new Date().toLocaleString()).setBackground('#0b5394').setFontColor('#fff').setFontWeight('bold').setHorizontalAlignment('center');
  let row = start + 1;
  for (let i = 0; i < groups.length; i += 2) {
    const a = _block_(sh, row, 1, groups[i]);
    const b = groups[i + 1] ? _block_(sh, row, 10, groups[i + 1]) : row + 2;
    row += Math.max(a, b) - row + 2;
  }
  sh.autoResizeColumns(1, Math.min(sh.getMaxColumns(), 17));
  sync.getRange('B5').setValue('Đã cập nhật Trang tính2: ' + groups.length + ' cụm, ' + groups.reduce(function(n, g) { return n + g.pages.length; }, 0) + ' Page.');
}
