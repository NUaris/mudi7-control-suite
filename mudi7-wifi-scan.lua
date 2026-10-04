local m=assert(loadfile('/etc/mudi7-management/radio-scan.lua'))()
if arg[1]=='worker' then m.run('wifi')
elseif arg[1]=='scan' then print(require'cjson'.encode(m.start('wifi')))
elseif arg[1]=='status' then print(require'cjson'.encode(m.status('wifi')))
else io.stderr:write('Usage: lua mudi7-wifi-scan.lua scan|status\n');os.exit(2) end
