#!/usr/bin/env python3
"""Linux man pages scraper (man7.org).

Covers ~800 of the most important Linux man pages organized by section:
  - man1: User commands
  - man2: System calls
  - man3: Library functions
  - man4: Devices
  - man5: File formats
  - man7: Overviews/conventions
  - man8: Admin commands

Rate limit: 1.5s between fetches
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class Man7Scraper(BaseScraper):
    """Scrape Linux man pages from man7.org."""

    SOURCES = {
        "man1": {
            "pages": {
                # Core utilities
                "https://man7.org/linux/man-pages/man1/ls.1.html": "ls - list directory contents",
                "https://man7.org/linux/man-pages/man1/cd.1p.html": "cd - change directory",
                "https://man7.org/linux/man-pages/man1/cp.1.html": "cp - copy files",
                "https://man7.org/linux/man-pages/man1/mv.1.html": "mv - move/rename files",
                "https://man7.org/linux/man-pages/man1/rm.1.html": "rm - remove files",
                "https://man7.org/linux/man-pages/man1/mkdir.1.html": "mkdir - make directories",
                "https://man7.org/linux/man-pages/man1/rmdir.1.html": "rmdir - remove directories",
                "https://man7.org/linux/man-pages/man1/touch.1.html": "touch - change file timestamps",
                "https://man7.org/linux/man-pages/man1/cat.1.html": "cat - concatenate files",
                "https://man7.org/linux/man-pages/man1/head.1.html": "head - output first part of files",
                "https://man7.org/linux/man-pages/man1/tail.1.html": "tail - output last part of files",
                "https://man7.org/linux/man-pages/man1/less.1.html": "less - pager",
                "https://man7.org/linux/man-pages/man1/more.1.html": "more - pager",
                "https://man7.org/linux/man-pages/man1/wc.1.html": "wc - word count",
                "https://man7.org/linux/man-pages/man1/sort.1.html": "sort - sort lines",
                "https://man7.org/linux/man-pages/man1/uniq.1.html": "uniq - unique lines",
                "https://man7.org/linux/man-pages/man1/cut.1.html": "cut - remove sections",
                "https://man7.org/linux/man-pages/man1/paste.1.html": "paste - merge lines",
                "https://man7.org/linux/man-pages/man1/tr.1.html": "tr - translate characters",
                "https://man7.org/linux/man-pages/man1/tee.1.html": "tee - read from stdin write to stdout and files",
                "https://man7.org/linux/man-pages/man1/ln.1.html": "ln - make links",
                "https://man7.org/linux/man-pages/man1/readlink.1.html": "readlink - print resolved symbolic links",
                "https://man7.org/linux/man-pages/man1/realpath.1.html": "realpath - print resolved path",
                "https://man7.org/linux/man-pages/man1/stat.1.html": "stat - display file status",
                "https://man7.org/linux/man-pages/man1/file.1.html": "file - determine file type",
                "https://man7.org/linux/man-pages/man1/dd.1.html": "dd - convert and copy a file",
                "https://man7.org/linux/man-pages/man1/df.1.html": "df - disk free",
                "https://man7.org/linux/man-pages/man1/du.1.html": "du - disk usage",
                "https://man7.org/linux/man-pages/man1/chmod.1.html": "chmod - change file mode",
                "https://man7.org/linux/man-pages/man1/chown.1.html": "chown - change file owner",
                "https://man7.org/linux/man-pages/man1/chgrp.1.html": "chgrp - change group",
                # Search and find
                "https://man7.org/linux/man-pages/man1/find.1.html": "find - search for files",
                "https://man7.org/linux/man-pages/man1/locate.1.html": "locate - find files by name",
                "https://man7.org/linux/man-pages/man1/which.1.html": "which - locate a command",
                "https://man7.org/linux/man-pages/man1/whereis.1.html": "whereis - locate binary/source/manual",
                "https://man7.org/linux/man-pages/man1/grep.1.html": "grep - print matching lines",
                "https://man7.org/linux/man-pages/man1/egrep.1.html": "egrep - extended grep",
                "https://man7.org/linux/man-pages/man1/fgrep.1.html": "fgrep - fixed string grep",
                "https://man7.org/linux/man-pages/man1/sed.1.html": "sed - stream editor",
                "https://man7.org/linux/man-pages/man1/awk.1p.html": "awk - pattern scanning",
                "https://man7.org/linux/man-pages/man1/xargs.1.html": "xargs - build and execute commands",
                # Text processing
                "https://man7.org/linux/man-pages/man1/diff.1.html": "diff - compare files",
                "https://man7.org/linux/man-pages/man1/patch.1.html": "patch - apply a diff file",
                "https://man7.org/linux/man-pages/man1/comm.1.html": "comm - compare sorted files",
                "https://man7.org/linux/man-pages/man1/join.1.html": "join - join lines on common field",
                "https://man7.org/linux/man-pages/man1/expand.1.html": "expand - convert tabs to spaces",
                "https://man7.org/linux/man-pages/man1/fold.1.html": "fold - wrap lines",
                "https://man7.org/linux/man-pages/man1/fmt.1.html": "fmt - simple text formatter",
                "https://man7.org/linux/man-pages/man1/nl.1.html": "nl - number lines",
                "https://man7.org/linux/man-pages/man1/pr.1.html": "pr - convert text for printing",
                "https://man7.org/linux/man-pages/man1/column.1.html": "column - columnate lists",
                # Compression and archiving
                "https://man7.org/linux/man-pages/man1/tar.1.html": "tar - tape archive",
                "https://man7.org/linux/man-pages/man1/gzip.1.html": "gzip - compress files",
                "https://man7.org/linux/man-pages/man1/gunzip.1.html": "gunzip - decompress files",
                "https://man7.org/linux/man-pages/man1/bzip2.1.html": "bzip2 - block-sorting compressor",
                "https://man7.org/linux/man-pages/man1/xz.1.html": "xz - compress files",
                "https://man7.org/linux/man-pages/man1/zip.1.html": "zip - package and compress",
                "https://man7.org/linux/man-pages/man1/unzip.1.html": "unzip - extract compressed files",
                "https://man7.org/linux/man-pages/man1/cpio.1.html": "cpio - copy files to/from archives",
                # Process management
                "https://man7.org/linux/man-pages/man1/ps.1.html": "ps - process status",
                "https://man7.org/linux/man-pages/man1/top.1.html": "top - display processes",
                "https://man7.org/linux/man-pages/man1/kill.1.html": "kill - send signal to process",
                "https://man7.org/linux/man-pages/man1/killall.1.html": "killall - kill processes by name",
                "https://man7.org/linux/man-pages/man1/pkill.1.html": "pkill - signal processes by pattern",
                "https://man7.org/linux/man-pages/man1/pgrep.1.html": "pgrep - look up processes",
                "https://man7.org/linux/man-pages/man1/nice.1.html": "nice - run with modified scheduling",
                "https://man7.org/linux/man-pages/man1/renice.1.html": "renice - alter priority",
                "https://man7.org/linux/man-pages/man1/nohup.1.html": "nohup - run immune to hangups",
                "https://man7.org/linux/man-pages/man1/timeout.1.html": "timeout - run with time limit",
                "https://man7.org/linux/man-pages/man1/watch.1.html": "watch - execute periodically",
                "https://man7.org/linux/man-pages/man1/time.1.html": "time - time a command",
                "https://man7.org/linux/man-pages/man1/strace.1.html": "strace - trace system calls",
                "https://man7.org/linux/man-pages/man1/ltrace.1.html": "ltrace - library call tracer",
                "https://man7.org/linux/man-pages/man1/lsof.1.html": "lsof - list open files",
                # Shell and scripting
                "https://man7.org/linux/man-pages/man1/bash.1.html": "bash - Bourne Again Shell",
                "https://man7.org/linux/man-pages/man1/sh.1p.html": "sh - shell",
                "https://man7.org/linux/man-pages/man1/env.1.html": "env - run in modified environment",
                "https://man7.org/linux/man-pages/man1/printenv.1.html": "printenv - print environment",
                "https://man7.org/linux/man-pages/man1/export.1p.html": "export - set export attribute",
                "https://man7.org/linux/man-pages/man1/echo.1.html": "echo - display a line of text",
                "https://man7.org/linux/man-pages/man1/printf.1.html": "printf - format and print",
                "https://man7.org/linux/man-pages/man1/test.1.html": "test - check file types",
                "https://man7.org/linux/man-pages/man1/expr.1.html": "expr - evaluate expressions",
                "https://man7.org/linux/man-pages/man1/seq.1.html": "seq - print sequence of numbers",
                "https://man7.org/linux/man-pages/man1/yes.1.html": "yes - output a string repeatedly",
                "https://man7.org/linux/man-pages/man1/true.1.html": "true - do nothing successfully",
                "https://man7.org/linux/man-pages/man1/false.1.html": "false - do nothing unsuccessfully",
                "https://man7.org/linux/man-pages/man1/sleep.1.html": "sleep - delay for specified time",
                # User and permissions
                "https://man7.org/linux/man-pages/man1/id.1.html": "id - print user identity",
                "https://man7.org/linux/man-pages/man1/whoami.1.html": "whoami - print effective user",
                "https://man7.org/linux/man-pages/man1/who.1.html": "who - show who is logged on",
                "https://man7.org/linux/man-pages/man1/w.1.html": "w - show who is logged on and what they are doing",
                "https://man7.org/linux/man-pages/man1/groups.1.html": "groups - print group names",
                "https://man7.org/linux/man-pages/man1/passwd.1.html": "passwd - change password",
                "https://man7.org/linux/man-pages/man1/su.1.html": "su - run as another user",
                "https://man7.org/linux/man-pages/man1/sudo.8.html": "sudo - execute as another user",
                "https://man7.org/linux/man-pages/man1/newgrp.1.html": "newgrp - change group",
                # Networking
                "https://man7.org/linux/man-pages/man1/ssh.1.html": "ssh - OpenSSH client",
                "https://man7.org/linux/man-pages/man1/scp.1.html": "scp - secure copy",
                "https://man7.org/linux/man-pages/man1/sftp.1.html": "sftp - secure file transfer",
                "https://man7.org/linux/man-pages/man1/rsync.1.html": "rsync - remote file sync",
                "https://man7.org/linux/man-pages/man1/curl.1.html": "curl - transfer a URL",
                "https://man7.org/linux/man-pages/man1/wget.1.html": "wget - non-interactive download",
                "https://man7.org/linux/man-pages/man1/nc.1.html": "nc - netcat",
                "https://man7.org/linux/man-pages/man1/hostname.1.html": "hostname - show/set system hostname",
                # Development
                "https://man7.org/linux/man-pages/man1/gcc.1.html": "gcc - GNU C compiler",
                "https://man7.org/linux/man-pages/man1/g++.1.html": "g++ - GNU C++ compiler",
                "https://man7.org/linux/man-pages/man1/make.1.html": "make - maintain program groups",
                "https://man7.org/linux/man-pages/man1/gdb.1.html": "gdb - GNU debugger",
                "https://man7.org/linux/man-pages/man1/ld.1.html": "ld - GNU linker",
                "https://man7.org/linux/man-pages/man1/nm.1.html": "nm - list symbols",
                "https://man7.org/linux/man-pages/man1/objdump.1.html": "objdump - display object file info",
                "https://man7.org/linux/man-pages/man1/readelf.1.html": "readelf - display ELF info",
                "https://man7.org/linux/man-pages/man1/strings.1.html": "strings - print printable strings",
                "https://man7.org/linux/man-pages/man1/strip.1.html": "strip - discard symbols",
                "https://man7.org/linux/man-pages/man1/ldd.1.html": "ldd - print shared library dependencies",
                "https://man7.org/linux/man-pages/man1/ar.1.html": "ar - create/modify archives",
                "https://man7.org/linux/man-pages/man1/git.1.html": "git - version control",
                # Misc important
                "https://man7.org/linux/man-pages/man1/man.1.html": "man - format and display manual pages",
                "https://man7.org/linux/man-pages/man1/apropos.1.html": "apropos - search manual page names",
                "https://man7.org/linux/man-pages/man1/whatis.1.html": "whatis - display one-line descriptions",
                "https://man7.org/linux/man-pages/man1/info.1.html": "info - read info documents",
                "https://man7.org/linux/man-pages/man1/date.1.html": "date - print/set system date",
                "https://man7.org/linux/man-pages/man1/cal.1.html": "cal - display a calendar",
                "https://man7.org/linux/man-pages/man1/uname.1.html": "uname - print system information",
                "https://man7.org/linux/man-pages/man1/uptime.1.html": "uptime - tell how long system has been running",
                "https://man7.org/linux/man-pages/man1/free.1.html": "free - display memory usage",
                "https://man7.org/linux/man-pages/man1/vmstat.8.html": "vmstat - virtual memory statistics",
                "https://man7.org/linux/man-pages/man1/iostat.1.html": "iostat - I/O statistics",
                "https://man7.org/linux/man-pages/man1/dmesg.1.html": "dmesg - print kernel ring buffer",
                "https://man7.org/linux/man-pages/man1/journalctl.1.html": "journalctl - query the journal",
                "https://man7.org/linux/man-pages/man1/systemctl.1.html": "systemctl - control systemd",
                "https://man7.org/linux/man-pages/man1/loginctl.1.html": "loginctl - control login manager",
                "https://man7.org/linux/man-pages/man1/timedatectl.1.html": "timedatectl - control time and date",
                "https://man7.org/linux/man-pages/man1/hostnamectl.1.html": "hostnamectl - control hostname",
                "https://man7.org/linux/man-pages/man1/localectl.1.html": "localectl - control locale",
                "https://man7.org/linux/man-pages/man1/crontab.1.html": "crontab - maintain cron tables",
                "https://man7.org/linux/man-pages/man1/at.1p.html": "at - execute commands at later time",
                "https://man7.org/linux/man-pages/man1/screen.1.html": "screen - terminal multiplexer",
                "https://man7.org/linux/man-pages/man1/tmux.1.html": "tmux - terminal multiplexer",
                "https://man7.org/linux/man-pages/man1/tput.1.html": "tput - initialize terminal",
                "https://man7.org/linux/man-pages/man1/stty.1.html": "stty - change terminal settings",
                "https://man7.org/linux/man-pages/man1/tty.1.html": "tty - print file name of terminal",
                "https://man7.org/linux/man-pages/man1/od.1.html": "od - dump files in octal",
                "https://man7.org/linux/man-pages/man1/hexdump.1.html": "hexdump - display file contents",
                "https://man7.org/linux/man-pages/man1/xxd.1.html": "xxd - hex dump",
                "https://man7.org/linux/man-pages/man1/base64.1.html": "base64 - encode/decode base64",
                "https://man7.org/linux/man-pages/man1/md5sum.1.html": "md5sum - compute MD5 digest",
                "https://man7.org/linux/man-pages/man1/sha256sum.1.html": "sha256sum - compute SHA256 digest",
                "https://man7.org/linux/man-pages/man1/sum.1.html": "sum - checksum and count blocks",
                "https://man7.org/linux/man-pages/man1/cksum.1.html": "cksum - checksum and count bytes",
            },
        },
        "man2": {
            "pages": {
                # Process
                "https://man7.org/linux/man-pages/man2/fork.2.html": "fork - create child process",
                "https://man7.org/linux/man-pages/man2/execve.2.html": "execve - execute program",
                "https://man7.org/linux/man-pages/man2/clone.2.html": "clone - create child process",
                "https://man7.org/linux/man-pages/man2/wait.2.html": "wait - wait for process",
                "https://man7.org/linux/man-pages/man2/waitpid.2.html": "waitpid - wait for specific process",
                "https://man7.org/linux/man-pages/man2/exit_group.2.html": "exit_group - exit all threads",
                "https://man7.org/linux/man-pages/man2/getpid.2.html": "getpid - get process ID",
                "https://man7.org/linux/man-pages/man2/getppid.2.html": "getppid - get parent PID",
                "https://man7.org/linux/man-pages/man2/getuid.2.html": "getuid - get user ID",
                "https://man7.org/linux/man-pages/man2/setuid.2.html": "setuid - set user ID",
                "https://man7.org/linux/man-pages/man2/getgid.2.html": "getgid - get group ID",
                "https://man7.org/linux/man-pages/man2/setgid.2.html": "setgid - set group ID",
                "https://man7.org/linux/man-pages/man2/setsid.2.html": "setsid - create session",
                "https://man7.org/linux/man-pages/man2/prctl.2.html": "prctl - process control",
                # File I/O
                "https://man7.org/linux/man-pages/man2/open.2.html": "open - open file",
                "https://man7.org/linux/man-pages/man2/close.2.html": "close - close file descriptor",
                "https://man7.org/linux/man-pages/man2/read.2.html": "read - read from file descriptor",
                "https://man7.org/linux/man-pages/man2/write.2.html": "write - write to file descriptor",
                "https://man7.org/linux/man-pages/man2/lseek.2.html": "lseek - seek in file",
                "https://man7.org/linux/man-pages/man2/pread.2.html": "pread/pwrite - read/write at offset",
                "https://man7.org/linux/man-pages/man2/readv.2.html": "readv/writev - scatter/gather I/O",
                "https://man7.org/linux/man-pages/man2/dup.2.html": "dup - duplicate file descriptor",
                "https://man7.org/linux/man-pages/man2/dup2.2.html": "dup2 - duplicate file descriptor",
                "https://man7.org/linux/man-pages/man2/fcntl.2.html": "fcntl - file control",
                "https://man7.org/linux/man-pages/man2/ioctl.2.html": "ioctl - device control",
                "https://man7.org/linux/man-pages/man2/flock.2.html": "flock - file lock",
                "https://man7.org/linux/man-pages/man2/stat.2.html": "stat - get file status",
                "https://man7.org/linux/man-pages/man2/fstat.2.html": "fstat - get file status",
                "https://man7.org/linux/man-pages/man2/lstat.2.html": "lstat - get link status",
                "https://man7.org/linux/man-pages/man2/access.2.html": "access - check file permissions",
                "https://man7.org/linux/man-pages/man2/truncate.2.html": "truncate - truncate file",
                "https://man7.org/linux/man-pages/man2/rename.2.html": "rename - rename file",
                "https://man7.org/linux/man-pages/man2/unlink.2.html": "unlink - delete name",
                "https://man7.org/linux/man-pages/man2/link.2.html": "link - make hard link",
                "https://man7.org/linux/man-pages/man2/symlink.2.html": "symlink - make symbolic link",
                "https://man7.org/linux/man-pages/man2/readlink.2.html": "readlink - read symbolic link",
                "https://man7.org/linux/man-pages/man2/mkdir.2.html": "mkdir - create directory",
                "https://man7.org/linux/man-pages/man2/rmdir.2.html": "rmdir - remove directory",
                "https://man7.org/linux/man-pages/man2/getdents.2.html": "getdents - get directory entries",
                "https://man7.org/linux/man-pages/man2/chdir.2.html": "chdir - change directory",
                "https://man7.org/linux/man-pages/man2/getcwd.2.html": "getcwd - get current directory",
                "https://man7.org/linux/man-pages/man2/chmod.2.html": "chmod - change file mode",
                "https://man7.org/linux/man-pages/man2/chown.2.html": "chown - change file owner",
                "https://man7.org/linux/man-pages/man2/umask.2.html": "umask - set file mode creation mask",
                # Memory
                "https://man7.org/linux/man-pages/man2/mmap.2.html": "mmap - map files or devices into memory",
                "https://man7.org/linux/man-pages/man2/munmap.2.html": "munmap - unmap memory",
                "https://man7.org/linux/man-pages/man2/mprotect.2.html": "mprotect - set memory protection",
                "https://man7.org/linux/man-pages/man2/brk.2.html": "brk/sbrk - change data segment size",
                "https://man7.org/linux/man-pages/man2/mlock.2.html": "mlock - lock memory",
                "https://man7.org/linux/man-pages/man2/msync.2.html": "msync - synchronize memory with file",
                "https://man7.org/linux/man-pages/man2/madvise.2.html": "madvise - give memory advice",
                # Signals
                "https://man7.org/linux/man-pages/man2/kill.2.html": "kill - send signal",
                "https://man7.org/linux/man-pages/man2/signal.2.html": "signal - ANSI C signal handling",
                "https://man7.org/linux/man-pages/man2/sigaction.2.html": "sigaction - examine/change signal",
                "https://man7.org/linux/man-pages/man2/sigprocmask.2.html": "sigprocmask - signal mask",
                "https://man7.org/linux/man-pages/man2/sigpending.2.html": "sigpending - examine pending signals",
                "https://man7.org/linux/man-pages/man2/sigsuspend.2.html": "sigsuspend - wait for signal",
                "https://man7.org/linux/man-pages/man2/signalfd.2.html": "signalfd - signal via file descriptor",
                # IPC
                "https://man7.org/linux/man-pages/man2/pipe.2.html": "pipe - create pipe",
                "https://man7.org/linux/man-pages/man2/socketpair.2.html": "socketpair - create socket pair",
                "https://man7.org/linux/man-pages/man2/shmget.2.html": "shmget - get shared memory",
                "https://man7.org/linux/man-pages/man2/shmat.2.html": "shmat - attach shared memory",
                "https://man7.org/linux/man-pages/man2/semget.2.html": "semget - get semaphore set",
                "https://man7.org/linux/man-pages/man2/semop.2.html": "semop - semaphore operations",
                "https://man7.org/linux/man-pages/man2/msgget.2.html": "msgget - get message queue",
                "https://man7.org/linux/man-pages/man2/msgsnd.2.html": "msgsnd - send message",
                "https://man7.org/linux/man-pages/man2/msgrcv.2.html": "msgrcv - receive message",
                # Networking
                "https://man7.org/linux/man-pages/man2/socket.2.html": "socket - create endpoint",
                "https://man7.org/linux/man-pages/man2/bind.2.html": "bind - bind name to socket",
                "https://man7.org/linux/man-pages/man2/listen.2.html": "listen - listen for connections",
                "https://man7.org/linux/man-pages/man2/accept.2.html": "accept - accept connection",
                "https://man7.org/linux/man-pages/man2/connect.2.html": "connect - initiate connection",
                "https://man7.org/linux/man-pages/man2/send.2.html": "send - send message on socket",
                "https://man7.org/linux/man-pages/man2/recv.2.html": "recv - receive from socket",
                "https://man7.org/linux/man-pages/man2/sendto.2.html": "sendto - send to address",
                "https://man7.org/linux/man-pages/man2/recvfrom.2.html": "recvfrom - receive from address",
                "https://man7.org/linux/man-pages/man2/sendmsg.2.html": "sendmsg - send message",
                "https://man7.org/linux/man-pages/man2/recvmsg.2.html": "recvmsg - receive message",
                "https://man7.org/linux/man-pages/man2/shutdown.2.html": "shutdown - shut down socket",
                "https://man7.org/linux/man-pages/man2/getsockopt.2.html": "getsockopt - get socket options",
                "https://man7.org/linux/man-pages/man2/setsockopt.2.html": "setsockopt - set socket options",
                "https://man7.org/linux/man-pages/man2/getsockname.2.html": "getsockname - get socket name",
                "https://man7.org/linux/man-pages/man2/getpeername.2.html": "getpeername - get peer name",
                # Polling and multiplexing
                "https://man7.org/linux/man-pages/man2/select.2.html": "select - synchronous I/O multiplexing",
                "https://man7.org/linux/man-pages/man2/poll.2.html": "poll - wait for events on file descriptors",
                "https://man7.org/linux/man-pages/man2/epoll_create.2.html": "epoll_create - open epoll file descriptor",
                "https://man7.org/linux/man-pages/man2/epoll_ctl.2.html": "epoll_ctl - control epoll",
                "https://man7.org/linux/man-pages/man2/epoll_wait.2.html": "epoll_wait - wait for epoll events",
                # Time
                "https://man7.org/linux/man-pages/man2/gettimeofday.2.html": "gettimeofday - get time",
                "https://man7.org/linux/man-pages/man2/clock_gettime.2.html": "clock_gettime - get clock time",
                "https://man7.org/linux/man-pages/man2/nanosleep.2.html": "nanosleep - high-resolution sleep",
                "https://man7.org/linux/man-pages/man2/timer_create.2.html": "timer_create - create POSIX timer",
                # Misc
                "https://man7.org/linux/man-pages/man2/mount.2.html": "mount - mount filesystem",
                "https://man7.org/linux/man-pages/man2/umount.2.html": "umount - unmount filesystem",
                "https://man7.org/linux/man-pages/man2/pivot_root.2.html": "pivot_root - change root filesystem",
                "https://man7.org/linux/man-pages/man2/chroot.2.html": "chroot - change root directory",
                "https://man7.org/linux/man-pages/man2/ptrace.2.html": "ptrace - process trace",
                "https://man7.org/linux/man-pages/man2/seccomp.2.html": "seccomp - secure computing mode",
                "https://man7.org/linux/man-pages/man2/futex.2.html": "futex - fast user-space locking",
                "https://man7.org/linux/man-pages/man2/eventfd.2.html": "eventfd - event notification",
                "https://man7.org/linux/man-pages/man2/timerfd_create.2.html": "timerfd_create - timer file descriptor",
                "https://man7.org/linux/man-pages/man2/inotify_init.2.html": "inotify_init - initialize inotify",
                "https://man7.org/linux/man-pages/man2/inotify_add_watch.2.html": "inotify_add_watch - add watch",
                "https://man7.org/linux/man-pages/man2/sendfile.2.html": "sendfile - transfer data between fds",
                "https://man7.org/linux/man-pages/man2/splice.2.html": "splice - splice data to/from pipe",
                "https://man7.org/linux/man-pages/man2/tee.2.html": "tee - duplicating pipe content",
                "https://man7.org/linux/man-pages/man2/io_uring_setup.2.html": "io_uring_setup - setup io_uring",
                "https://man7.org/linux/man-pages/man2/io_uring_enter.2.html": "io_uring_enter - enter io_uring",
                "https://man7.org/linux/man-pages/man2/bpf.2.html": "bpf - BPF system call",
                "https://man7.org/linux/man-pages/man2/perf_event_open.2.html": "perf_event_open - perf monitoring",
                "https://man7.org/linux/man-pages/man2/sysinfo.2.html": "sysinfo - system information",
                "https://man7.org/linux/man-pages/man2/reboot.2.html": "reboot - reboot or power off",
            },
        },
        "man3": {
            "pages": {
                # Standard I/O
                "https://man7.org/linux/man-pages/man3/printf.3.html": "printf - formatted output",
                "https://man7.org/linux/man-pages/man3/fprintf.3.html": "fprintf - formatted file output",
                "https://man7.org/linux/man-pages/man3/sprintf.3.html": "sprintf - formatted string output",
                "https://man7.org/linux/man-pages/man3/snprintf.3.html": "snprintf - safe formatted output",
                "https://man7.org/linux/man-pages/man3/scanf.3.html": "scanf - formatted input",
                "https://man7.org/linux/man-pages/man3/fopen.3.html": "fopen - open stream",
                "https://man7.org/linux/man-pages/man3/fclose.3.html": "fclose - close stream",
                "https://man7.org/linux/man-pages/man3/fread.3.html": "fread - binary stream I/O",
                "https://man7.org/linux/man-pages/man3/fwrite.3.html": "fwrite - binary stream output",
                "https://man7.org/linux/man-pages/man3/fgets.3.html": "fgets - get string from stream",
                "https://man7.org/linux/man-pages/man3/fputs.3.html": "fputs - put string to stream",
                "https://man7.org/linux/man-pages/man3/fseek.3.html": "fseek - seek in stream",
                "https://man7.org/linux/man-pages/man3/ftell.3.html": "ftell - stream position",
                "https://man7.org/linux/man-pages/man3/fflush.3.html": "fflush - flush stream",
                "https://man7.org/linux/man-pages/man3/feof.3.html": "feof - test end of file",
                "https://man7.org/linux/man-pages/man3/ferror.3.html": "ferror - test error",
                "https://man7.org/linux/man-pages/man3/getline.3.html": "getline - delimited string input",
                "https://man7.org/linux/man-pages/man3/perror.3.html": "perror - print error message",
                "https://man7.org/linux/man-pages/man3/strerror.3.html": "strerror - string error message",
                # Memory allocation
                "https://man7.org/linux/man-pages/man3/malloc.3.html": "malloc - allocate memory",
                "https://man7.org/linux/man-pages/man3/calloc.3.html": "calloc - allocate zeroed memory",
                "https://man7.org/linux/man-pages/man3/realloc.3.html": "realloc - resize memory",
                "https://man7.org/linux/man-pages/man3/free.3.html": "free - free memory",
                "https://man7.org/linux/man-pages/man3/posix_memalign.3.html": "posix_memalign - aligned alloc",
                # String functions
                "https://man7.org/linux/man-pages/man3/strlen.3.html": "strlen - string length",
                "https://man7.org/linux/man-pages/man3/strcpy.3.html": "strcpy - copy string",
                "https://man7.org/linux/man-pages/man3/strncpy.3.html": "strncpy - copy string with limit",
                "https://man7.org/linux/man-pages/man3/strcat.3.html": "strcat - concatenate strings",
                "https://man7.org/linux/man-pages/man3/strncat.3.html": "strncat - concatenate with limit",
                "https://man7.org/linux/man-pages/man3/strcmp.3.html": "strcmp - compare strings",
                "https://man7.org/linux/man-pages/man3/strncmp.3.html": "strncmp - compare with limit",
                "https://man7.org/linux/man-pages/man3/strchr.3.html": "strchr - locate character",
                "https://man7.org/linux/man-pages/man3/strrchr.3.html": "strrchr - locate last character",
                "https://man7.org/linux/man-pages/man3/strstr.3.html": "strstr - locate substring",
                "https://man7.org/linux/man-pages/man3/strtok.3.html": "strtok - tokenize string",
                "https://man7.org/linux/man-pages/man3/strdup.3.html": "strdup - duplicate string",
                "https://man7.org/linux/man-pages/man3/memcpy.3.html": "memcpy - copy memory",
                "https://man7.org/linux/man-pages/man3/memmove.3.html": "memmove - copy memory (overlap-safe)",
                "https://man7.org/linux/man-pages/man3/memset.3.html": "memset - fill memory",
                "https://man7.org/linux/man-pages/man3/memcmp.3.html": "memcmp - compare memory",
                # Conversion
                "https://man7.org/linux/man-pages/man3/atoi.3.html": "atoi - convert string to integer",
                "https://man7.org/linux/man-pages/man3/atol.3.html": "atol - convert string to long",
                "https://man7.org/linux/man-pages/man3/atof.3.html": "atof - convert string to double",
                "https://man7.org/linux/man-pages/man3/strtol.3.html": "strtol - convert string to long",
                "https://man7.org/linux/man-pages/man3/strtoul.3.html": "strtoul - convert to unsigned long",
                "https://man7.org/linux/man-pages/man3/strtod.3.html": "strtod - convert to double",
                # Math
                "https://man7.org/linux/man-pages/man3/abs.3.html": "abs - absolute value",
                "https://man7.org/linux/man-pages/man3/ceil.3.html": "ceil - ceiling function",
                "https://man7.org/linux/man-pages/man3/floor.3.html": "floor - floor function",
                "https://man7.org/linux/man-pages/man3/sqrt.3.html": "sqrt - square root",
                "https://man7.org/linux/man-pages/man3/pow.3.html": "pow - power function",
                "https://man7.org/linux/man-pages/man3/log.3.html": "log - natural logarithm",
                "https://man7.org/linux/man-pages/man3/sin.3.html": "sin - sine function",
                "https://man7.org/linux/man-pages/man3/cos.3.html": "cos - cosine function",
                "https://man7.org/linux/man-pages/man3/rand.3.html": "rand - random number",
                "https://man7.org/linux/man-pages/man3/srand.3.html": "srand - seed random",
                # Process/System
                "https://man7.org/linux/man-pages/man3/system.3.html": "system - execute shell command",
                "https://man7.org/linux/man-pages/man3/popen.3.html": "popen - pipe to/from process",
                "https://man7.org/linux/man-pages/man3/exec.3.html": "exec - execute file",
                "https://man7.org/linux/man-pages/man3/exit.3.html": "exit - terminate process",
                "https://man7.org/linux/man-pages/man3/atexit.3.html": "atexit - register exit function",
                "https://man7.org/linux/man-pages/man3/getenv.3.html": "getenv - get environment variable",
                "https://man7.org/linux/man-pages/man3/setenv.3.html": "setenv - set environment variable",
                "https://man7.org/linux/man-pages/man3/getopt.3.html": "getopt - parse options",
                "https://man7.org/linux/man-pages/man3/getopt_long.3.html": "getopt_long - parse long options",
                "https://man7.org/linux/man-pages/man3/glob.3.html": "glob - pathname matching",
                "https://man7.org/linux/man-pages/man3/regex.3.html": "regex - POSIX regex",
                "https://man7.org/linux/man-pages/man3/dlopen.3.html": "dlopen - open shared library",
                "https://man7.org/linux/man-pages/man3/dlsym.3.html": "dlsym - obtain symbol address",
                # Thread (pthread)
                "https://man7.org/linux/man-pages/man3/pthread_create.3.html": "pthread_create - create thread",
                "https://man7.org/linux/man-pages/man3/pthread_join.3.html": "pthread_join - join thread",
                "https://man7.org/linux/man-pages/man3/pthread_exit.3.html": "pthread_exit - terminate thread",
                "https://man7.org/linux/man-pages/man3/pthread_mutex_init.3.html": "pthread_mutex_init - init mutex",
                "https://man7.org/linux/man-pages/man3/pthread_mutex_lock.3.html": "pthread_mutex_lock - lock mutex",
                "https://man7.org/linux/man-pages/man3/pthread_mutex_unlock.3.html": "pthread_mutex_unlock - unlock mutex",
                "https://man7.org/linux/man-pages/man3/pthread_cond_init.3.html": "pthread_cond_init - init condition",
                "https://man7.org/linux/man-pages/man3/pthread_cond_wait.3.html": "pthread_cond_wait - wait on condition",
                "https://man7.org/linux/man-pages/man3/pthread_cond_signal.3.html": "pthread_cond_signal - signal condition",
                # Networking
                "https://man7.org/linux/man-pages/man3/getaddrinfo.3.html": "getaddrinfo - network address lookup",
                "https://man7.org/linux/man-pages/man3/getnameinfo.3.html": "getnameinfo - address to name",
                "https://man7.org/linux/man-pages/man3/gethostbyname.3.html": "gethostbyname - get host entry",
                "https://man7.org/linux/man-pages/man3/inet_pton.3.html": "inet_pton - text to binary address",
                "https://man7.org/linux/man-pages/man3/inet_ntop.3.html": "inet_ntop - binary to text address",
                "https://man7.org/linux/man-pages/man3/htons.3.html": "htons - byte order conversion",
                # Time
                "https://man7.org/linux/man-pages/man3/time.3.html": "time - get time",
                "https://man7.org/linux/man-pages/man3/localtime.3.html": "localtime - local time conversion",
                "https://man7.org/linux/man-pages/man3/gmtime.3.html": "gmtime - UTC time conversion",
                "https://man7.org/linux/man-pages/man3/strftime.3.html": "strftime - format time",
                "https://man7.org/linux/man-pages/man3/mktime.3.html": "mktime - convert to time_t",
                "https://man7.org/linux/man-pages/man3/difftime.3.html": "difftime - time difference",
                # Directory
                "https://man7.org/linux/man-pages/man3/opendir.3.html": "opendir - open directory",
                "https://man7.org/linux/man-pages/man3/readdir.3.html": "readdir - read directory",
                "https://man7.org/linux/man-pages/man3/closedir.3.html": "closedir - close directory",
                "https://man7.org/linux/man-pages/man3/scandir.3.html": "scandir - scan directory",
                # Error handling
                "https://man7.org/linux/man-pages/man3/errno.3.html": "errno - error number",
                "https://man7.org/linux/man-pages/man3/assert.3.html": "assert - abort on false",
            },
        },
        "man4": {
            "pages": {
                "https://man7.org/linux/man-pages/man4/null.4.html": "null - data sink",
                "https://man7.org/linux/man-pages/man4/zero.4.html": "zero - zero source",
                "https://man7.org/linux/man-pages/man4/random.4.html": "random - kernel random source",
                "https://man7.org/linux/man-pages/man4/urandom.4.html": "urandom - non-blocking random",
                "https://man7.org/linux/man-pages/man4/full.4.html": "full - always full device",
                "https://man7.org/linux/man-pages/man4/tty.4.html": "tty - controlling terminal",
                "https://man7.org/linux/man-pages/man4/console.4.html": "console - console terminal",
                "https://man7.org/linux/man-pages/man4/pts.4.html": "pts - pseudoterminal slave",
                "https://man7.org/linux/man-pages/man4/ptmx.4.html": "ptmx - pseudoterminal master",
                "https://man7.org/linux/man-pages/man4/loop.4.html": "loop - loop devices",
                "https://man7.org/linux/man-pages/man4/mem.4.html": "mem - system memory",
                "https://man7.org/linux/man-pages/man4/sd.4.html": "sd - SCSI disk driver",
                "https://man7.org/linux/man-pages/man4/ttyS.4.html": "ttyS - serial terminal",
                "https://man7.org/linux/man-pages/man4/hd.4.html": "hd - MFM/IDE hard disk",
                "https://man7.org/linux/man-pages/man4/lp.4.html": "lp - line printer",
                "https://man7.org/linux/man-pages/man4/vcs.4.html": "vcs - virtual console memory",
                "https://man7.org/linux/man-pages/man4/fd.4.html": "fd - floppy disk device",
            },
        },
        "man5": {
            "pages": {
                "https://man7.org/linux/man-pages/man5/passwd.5.html": "passwd - password file",
                "https://man7.org/linux/man-pages/man5/shadow.5.html": "shadow - shadow password file",
                "https://man7.org/linux/man-pages/man5/group.5.html": "group - group file",
                "https://man7.org/linux/man-pages/man5/fstab.5.html": "fstab - filesystem table",
                "https://man7.org/linux/man-pages/man5/hosts.5.html": "hosts - static hostname lookup",
                "https://man7.org/linux/man-pages/man5/resolv.conf.5.html": "resolv.conf - resolver config",
                "https://man7.org/linux/man-pages/man5/nsswitch.conf.5.html": "nsswitch.conf - name service switch",
                "https://man7.org/linux/man-pages/man5/hostname.5.html": "hostname - local hostname",
                "https://man7.org/linux/man-pages/man5/host.conf.5.html": "host.conf - resolver config",
                "https://man7.org/linux/man-pages/man5/crontab.5.html": "crontab - cron table format",
                "https://man7.org/linux/man-pages/man5/inittab.5.html": "inittab - init configuration",
                "https://man7.org/linux/man-pages/man5/sysctl.conf.5.html": "sysctl.conf - sysctl preload",
                "https://man7.org/linux/man-pages/man5/proc.5.html": "proc - process information pseudo-filesystem",
                "https://man7.org/linux/man-pages/man5/sysfs.5.html": "sysfs - filesystem for kernel objects",
                "https://man7.org/linux/man-pages/man5/elf.5.html": "elf - Executable and Linkable Format",
                "https://man7.org/linux/man-pages/man5/core.5.html": "core - core dump file",
                "https://man7.org/linux/man-pages/man5/termcap.5.html": "termcap - terminal capability",
                "https://man7.org/linux/man-pages/man5/shells.5.html": "shells - valid login shells",
                "https://man7.org/linux/man-pages/man5/services.5.html": "services - Internet network services",
                "https://man7.org/linux/man-pages/man5/protocols.5.html": "protocols - network protocols",
                "https://man7.org/linux/man-pages/man5/locale.5.html": "locale - locale definition file",
                "https://man7.org/linux/man-pages/man5/filesystems.5.html": "filesystems - Linux filesystem types",
                "https://man7.org/linux/man-pages/man5/exports.5.html": "exports - NFS share list",
                "https://man7.org/linux/man-pages/man5/dir_colors.5.html": "dir_colors - color setup for ls",
                "https://man7.org/linux/man-pages/man5/issue.5.html": "issue - pre-login message",
                "https://man7.org/linux/man-pages/man5/motd.5.html": "motd - message of the day",
                "https://man7.org/linux/man-pages/man5/login.defs.5.html": "login.defs - login defaults",
                "https://man7.org/linux/man-pages/man5/limits.conf.5.html": "limits.conf - PAM resource limits",
                "https://man7.org/linux/man-pages/man5/systemd.unit.5.html": "systemd.unit - unit configuration",
                "https://man7.org/linux/man-pages/man5/systemd.service.5.html": "systemd.service - service unit",
                "https://man7.org/linux/man-pages/man5/systemd.timer.5.html": "systemd.timer - timer unit",
                "https://man7.org/linux/man-pages/man5/systemd.socket.5.html": "systemd.socket - socket unit",
                "https://man7.org/linux/man-pages/man5/systemd.mount.5.html": "systemd.mount - mount unit",
                "https://man7.org/linux/man-pages/man5/systemd.exec.5.html": "systemd.exec - execution environment",
                "https://man7.org/linux/man-pages/man5/journald.conf.5.html": "journald.conf - journal config",
                "https://man7.org/linux/man-pages/man5/logind.conf.5.html": "logind.conf - login manager config",
                "https://man7.org/linux/man-pages/man5/tmpfiles.d.5.html": "tmpfiles.d - temp file management",
                "https://man7.org/linux/man-pages/man5/sshd_config.5.html": "sshd_config - SSH daemon config",
                "https://man7.org/linux/man-pages/man5/ssh_config.5.html": "ssh_config - SSH client config",
            },
        },
        "man7": {
            "pages": {
                "https://man7.org/linux/man-pages/man7/man-pages.7.html": "man-pages - conventions",
                "https://man7.org/linux/man-pages/man7/signal.7.html": "signal - overview of signals",
                "https://man7.org/linux/man-pages/man7/socket.7.html": "socket - Linux socket interface",
                "https://man7.org/linux/man-pages/man7/tcp.7.html": "tcp - TCP protocol",
                "https://man7.org/linux/man-pages/man7/udp.7.html": "udp - UDP protocol",
                "https://man7.org/linux/man-pages/man7/ip.7.html": "ip - Linux IPv4 protocol",
                "https://man7.org/linux/man-pages/man7/ipv6.7.html": "ipv6 - Linux IPv6 protocol",
                "https://man7.org/linux/man-pages/man7/unix.7.html": "unix - Unix domain sockets",
                "https://man7.org/linux/man-pages/man7/netlink.7.html": "netlink - netlink protocol",
                "https://man7.org/linux/man-pages/man7/packet.7.html": "packet - packet interface",
                "https://man7.org/linux/man-pages/man7/raw.7.html": "raw - raw sockets",
                "https://man7.org/linux/man-pages/man7/epoll.7.html": "epoll - I/O event notification",
                "https://man7.org/linux/man-pages/man7/inotify.7.html": "inotify - filesystem events",
                "https://man7.org/linux/man-pages/man7/fanotify.7.html": "fanotify - filesystem notifications",
                "https://man7.org/linux/man-pages/man7/pipe.7.html": "pipe - overview of pipes",
                "https://man7.org/linux/man-pages/man7/fifo.7.html": "fifo - first-in first-out",
                "https://man7.org/linux/man-pages/man7/shm_overview.7.html": "shm_overview - shared memory",
                "https://man7.org/linux/man-pages/man7/sem_overview.7.html": "sem_overview - semaphores",
                "https://man7.org/linux/man-pages/man7/mq_overview.7.html": "mq_overview - message queues",
                "https://man7.org/linux/man-pages/man7/sysvipc.7.html": "sysvipc - System V IPC",
                "https://man7.org/linux/man-pages/man7/pthreads.7.html": "pthreads - POSIX threads",
                "https://man7.org/linux/man-pages/man7/futex.7.html": "futex - fast user-space locking",
                "https://man7.org/linux/man-pages/man7/capabilities.7.html": "capabilities - Linux capabilities",
                "https://man7.org/linux/man-pages/man7/credentials.7.html": "credentials - process identifiers",
                "https://man7.org/linux/man-pages/man7/namespaces.7.html": "namespaces - Linux namespaces",
                "https://man7.org/linux/man-pages/man7/cgroups.7.html": "cgroups - control groups",
                "https://man7.org/linux/man-pages/man7/pid_namespaces.7.html": "pid_namespaces - PID namespaces",
                "https://man7.org/linux/man-pages/man7/user_namespaces.7.html": "user_namespaces - user namespaces",
                "https://man7.org/linux/man-pages/man7/mount_namespaces.7.html": "mount_namespaces - mount namespaces",
                "https://man7.org/linux/man-pages/man7/network_namespaces.7.html": "network_namespaces - network ns",
                "https://man7.org/linux/man-pages/man7/path_resolution.7.html": "path_resolution - how paths are resolved",
                "https://man7.org/linux/man-pages/man7/glob.7.html": "glob - globbing pathnames",
                "https://man7.org/linux/man-pages/man7/regex.7.html": "regex - POSIX regular expressions",
                "https://man7.org/linux/man-pages/man7/utf-8.7.html": "utf-8 - UTF-8 encoding",
                "https://man7.org/linux/man-pages/man7/ascii.7.html": "ascii - ASCII character set",
                "https://man7.org/linux/man-pages/man7/charsets.7.html": "charsets - character set standards",
                "https://man7.org/linux/man-pages/man7/locale.7.html": "locale - description of locales",
                "https://man7.org/linux/man-pages/man7/environ.7.html": "environ - user environment",
                "https://man7.org/linux/man-pages/man7/hier.7.html": "hier - filesystem hierarchy",
                "https://man7.org/linux/man-pages/man7/feature_test_macros.7.html": "feature_test_macros - feature macros",
                "https://man7.org/linux/man-pages/man7/standards.7.html": "standards - POSIX standards",
                "https://man7.org/linux/man-pages/man7/arp.7.html": "arp - ARP protocol",
                "https://man7.org/linux/man-pages/man7/icmp.7.html": "icmp - ICMP protocol",
                "https://man7.org/linux/man-pages/man7/boot.7.html": "boot - system boot process",
                "https://man7.org/linux/man-pages/man7/time.7.html": "time - overview of time",
                "https://man7.org/linux/man-pages/man7/symlink.7.html": "symlink - symbolic link handling",
                "https://man7.org/linux/man-pages/man7/xattr.7.html": "xattr - extended attributes",
                "https://man7.org/linux/man-pages/man7/aio.7.html": "aio - POSIX async I/O",
                "https://man7.org/linux/man-pages/man7/io_uring.7.html": "io_uring - async I/O interface",
                "https://man7.org/linux/man-pages/man7/bpf-helpers.7.html": "bpf-helpers - BPF helper functions",
            },
        },
        "man8": {
            "pages": {
                "https://man7.org/linux/man-pages/man8/ifconfig.8.html": "ifconfig - configure network interface",
                "https://man7.org/linux/man-pages/man8/ip.8.html": "ip - show/manipulate routing/devices",
                "https://man7.org/linux/man-pages/man8/ip-address.8.html": "ip-address - protocol address management",
                "https://man7.org/linux/man-pages/man8/ip-route.8.html": "ip-route - routing table management",
                "https://man7.org/linux/man-pages/man8/ip-link.8.html": "ip-link - network device config",
                "https://man7.org/linux/man-pages/man8/ip-netns.8.html": "ip-netns - network namespace",
                "https://man7.org/linux/man-pages/man8/iptables.8.html": "iptables - IPv4 packet filter",
                "https://man7.org/linux/man-pages/man8/ip6tables.8.html": "ip6tables - IPv6 packet filter",
                "https://man7.org/linux/man-pages/man8/nft.8.html": "nft - nftables administration",
                "https://man7.org/linux/man-pages/man8/tc.8.html": "tc - traffic control",
                "https://man7.org/linux/man-pages/man8/ss.8.html": "ss - socket statistics",
                "https://man7.org/linux/man-pages/man8/netstat.8.html": "netstat - network statistics",
                "https://man7.org/linux/man-pages/man8/route.8.html": "route - show/manipulate IP routing",
                "https://man7.org/linux/man-pages/man8/ping.8.html": "ping - send ICMP ECHO_REQUEST",
                "https://man7.org/linux/man-pages/man8/traceroute.8.html": "traceroute - print route packets take",
                "https://man7.org/linux/man-pages/man8/arp.8.html": "arp - manipulate ARP cache",
                "https://man7.org/linux/man-pages/man8/ethtool.8.html": "ethtool - query/control NIC settings",
                "https://man7.org/linux/man-pages/man8/brctl.8.html": "brctl - ethernet bridge admin",
                "https://man7.org/linux/man-pages/man8/iwconfig.8.html": "iwconfig - wireless config",
                "https://man7.org/linux/man-pages/man8/iw.8.html": "iw - show/manipulate wireless",
                # Disk and filesystem
                "https://man7.org/linux/man-pages/man8/mount.8.html": "mount - mount filesystem",
                "https://man7.org/linux/man-pages/man8/umount.8.html": "umount - unmount filesystem",
                "https://man7.org/linux/man-pages/man8/fdisk.8.html": "fdisk - partition table manipulator",
                "https://man7.org/linux/man-pages/man8/parted.8.html": "parted - partition editor",
                "https://man7.org/linux/man-pages/man8/mkfs.8.html": "mkfs - build filesystem",
                "https://man7.org/linux/man-pages/man8/fsck.8.html": "fsck - check filesystem",
                "https://man7.org/linux/man-pages/man8/blkid.8.html": "blkid - block device attributes",
                "https://man7.org/linux/man-pages/man8/lsblk.8.html": "lsblk - list block devices",
                "https://man7.org/linux/man-pages/man8/tune2fs.8.html": "tune2fs - adjust ext filesystem",
                "https://man7.org/linux/man-pages/man8/resize2fs.8.html": "resize2fs - resize ext filesystem",
                "https://man7.org/linux/man-pages/man8/mkswap.8.html": "mkswap - set up swap area",
                "https://man7.org/linux/man-pages/man8/swapon.8.html": "swapon - enable swap",
                "https://man7.org/linux/man-pages/man8/swapoff.8.html": "swapoff - disable swap",
                # LVM
                "https://man7.org/linux/man-pages/man8/lvm.8.html": "lvm - LVM tools",
                "https://man7.org/linux/man-pages/man8/pvcreate.8.html": "pvcreate - create physical volume",
                "https://man7.org/linux/man-pages/man8/vgcreate.8.html": "vgcreate - create volume group",
                "https://man7.org/linux/man-pages/man8/lvcreate.8.html": "lvcreate - create logical volume",
                "https://man7.org/linux/man-pages/man8/pvs.8.html": "pvs - display physical volumes",
                "https://man7.org/linux/man-pages/man8/vgs.8.html": "vgs - display volume groups",
                "https://man7.org/linux/man-pages/man8/lvs.8.html": "lvs - display logical volumes",
                # System admin
                "https://man7.org/linux/man-pages/man8/useradd.8.html": "useradd - create user account",
                "https://man7.org/linux/man-pages/man8/usermod.8.html": "usermod - modify user account",
                "https://man7.org/linux/man-pages/man8/userdel.8.html": "userdel - delete user account",
                "https://man7.org/linux/man-pages/man8/groupadd.8.html": "groupadd - create group",
                "https://man7.org/linux/man-pages/man8/groupmod.8.html": "groupmod - modify group",
                "https://man7.org/linux/man-pages/man8/groupdel.8.html": "groupdel - delete group",
                "https://man7.org/linux/man-pages/man8/chpasswd.8.html": "chpasswd - update passwords in batch",
                "https://man7.org/linux/man-pages/man8/visudo.8.html": "visudo - edit sudoers safely",
                "https://man7.org/linux/man-pages/man8/cron.8.html": "cron - daemon for scheduled commands",
                "https://man7.org/linux/man-pages/man8/sshd.8.html": "sshd - OpenSSH daemon",
                "https://man7.org/linux/man-pages/man8/systemd.8.html": "systemd - system and service manager",
                "https://man7.org/linux/man-pages/man8/init.8.html": "init - systemd system manager",
                "https://man7.org/linux/man-pages/man8/shutdown.8.html": "shutdown - halt/power-off/reboot",
                "https://man7.org/linux/man-pages/man8/reboot.8.html": "reboot - halt/power-off/reboot",
                "https://man7.org/linux/man-pages/man8/dmesg.8.html": "dmesg - print kernel messages",
                "https://man7.org/linux/man-pages/man8/sysctl.8.html": "sysctl - configure kernel parameters",
                "https://man7.org/linux/man-pages/man8/modprobe.8.html": "modprobe - add/remove kernel modules",
                "https://man7.org/linux/man-pages/man8/lsmod.8.html": "lsmod - show loaded modules",
                "https://man7.org/linux/man-pages/man8/insmod.8.html": "insmod - insert module",
                "https://man7.org/linux/man-pages/man8/rmmod.8.html": "rmmod - remove module",
                "https://man7.org/linux/man-pages/man8/depmod.8.html": "depmod - module dependencies",
                "https://man7.org/linux/man-pages/man8/lspci.8.html": "lspci - list PCI devices",
                "https://man7.org/linux/man-pages/man8/lsusb.8.html": "lsusb - list USB devices",
                "https://man7.org/linux/man-pages/man8/hdparm.8.html": "hdparm - get/set hard disk parameters",
                "https://man7.org/linux/man-pages/man8/smartctl.8.html": "smartctl - SMART disk monitoring",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"man7-{source_key}" if source_key else "man7"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - Linux manual page', ' - man7.org']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"man7-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping man7/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    Man7Scraper(base, source_key).run()
