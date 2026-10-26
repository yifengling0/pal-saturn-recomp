package org.palsaturn.android;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.nio.channels.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.*;

/** Platform-independent, bounded-memory import. Original documents and saves are never modified. */
public final class DiscImport {
    static final long[] PAL_TOC = {0,132138,144036,154279,164654,176293,187263,197931,206294,219441,222337,223840,235392};
    static final long PAL_SECTORS = 243793;
    public interface Source { String name(); long size(); InputStream open() throws IOException; }
    public interface Progress { void update(String label); }
    static final Pattern FILE = Pattern.compile("(?i)^\\s*FILE\\s+(?:\"([^\"]+)\"|(\\S+))\\s+(\\S+)\\s*$");
    static final Pattern TRACK = Pattern.compile("(?i)^\\s*TRACK\\s+(\\d+)\\s+(\\S+)\\s*$");
    static void check(AtomicBoolean cancel) throws IOException {
        if (cancel.get() || Thread.currentThread().isInterrupted()) throw new InterruptedIOException("已取消导入，旧资源和存档未改变");
    }
    static String safe(String name) throws IOException {
        String n = name.replace('\\', '/');
        if (n.startsWith("/") || n.contains(":") || n.indexOf('\0') >= 0) throw new IOException("不安全的资源路径：" + name);
        ArrayList<String> parts = new ArrayList<>();
        for (String p : n.split("/")) {
            if (p.equals("..")) throw new IOException("CUE不能引用所选目录之外：" + name);
            if (!p.isEmpty() && !p.equals(".")) parts.add(p);
        }
        if (parts.isEmpty()) throw new IOException("空资源名称");
        return String.join("/", parts);
    }
    static byte[] readSmall(Source s) throws IOException {
        try (InputStream in=s.open(); ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] buf=new byte[8192]; int n;
            while ((n=in.read(buf))!=-1) { if (out.size()+n>1024*1024) throw new IOException("CUE过大（上限1 MiB）"); out.write(buf,0,n); }
            return out.toByteArray();
        }
    }
    public static File current(File home) throws IOException {
        File pointer=new File(home,"current");
        if (!pointer.isFile()) return null;
        String id=new String(Files.readAllBytes(pointer.toPath()), StandardCharsets.UTF_8).trim();
        if (!id.matches("disc-[a-f0-9-]+")) throw new IOException("资源索引损坏，请重新导入");
        File cue=new File(new File(home,id),"disc.cue");
        return cue.isFile()?cue:null;
    }
    public static File run(File home, List<Source> sources, AtomicBoolean cancel, Progress progress) throws IOException {
        return runWithLayout(home,sources,cancel,progress,PAL_TOC,PAL_SECTORS);
    }
    // Package-private layout injection lets pure-Java tests use tiny synthetic discs.
    static File runWithLayout(File home, List<Source> sources, AtomicBoolean cancel, Progress progress,long[] expectedToc,long expectedSectors) throws IOException {
        home.mkdirs();
        try (RandomAccessFile guard=new RandomAccessFile(new File(home,"resource.lock"),"rw"); FileChannel channel=guard.getChannel()) {
            FileLock lock;
            try {lock=channel.tryLock();}catch(OverlappingFileLockException e){throw new IOException("已有导入或游戏正在运行，请先退出游戏");}
            if(lock==null)throw new IOException("游戏正在运行，请从游戏菜单退出后再导入");
            try {return importLocked(home,sources,cancel,progress,expectedToc,expectedSectors);}finally{lock.release();}
        }
    }
    /** Called once on cold launcher start, never during a game or another import. */
    public static void cleanup(File home) {
        home.mkdirs();
        try(RandomAccessFile g=new RandomAccessFile(new File(home,"resource.lock"),"rw");FileChannel c=g.getChannel();FileLock lock=c.tryLock()) {
            if(lock==null)return;
            File selected=current(home);File keep=selected==null?null:selected.getParentFile();
            File[] all=home.listFiles();if(all==null)return;
            for(File f:all)if(f.isDirectory()&&(f.getName().startsWith("pending-")||f.getName().startsWith("disc-")&&!f.equals(keep)))remove(f);
        }catch(IOException|OverlappingFileLockException ignored){}
    }
    private static File importLocked(File home, List<Source> sources, AtomicBoolean cancel, Progress progress,long[] expectedToc,long expectedSectors) throws IOException {
        if (!home.isDirectory() && !home.mkdirs()) throw new IOException("无法创建私有资源目录");
        Map<String,Source> byName=new LinkedHashMap<>();
        Source cue=null;
        for(Source s:sources) {
            String name=safe(s.name()); String key=name.toLowerCase(Locale.ROOT);
            if (byName.put(key,s)!=null) throw new IOException("文件名大小写冲突："+name);
            if (key.endsWith(".cue")) { if(cue!=null) throw new IOException("请选择一张光盘：只能包含一个CUE文件"); cue=s; }
        }
        if(cue==null) throw new IOException("缺少CUE，请同时选择CUE及其全部BIN轨道，或选择所在文件夹");
        String cueName=safe(cue.name());
        String base=cueName.contains("/")?cueName.substring(0,cueName.lastIndexOf('/')+1):"";
        byte[] cueBytes=readSmall(cue);
        String text=new String(cueBytes,StandardCharsets.UTF_8);
        if(text.indexOf('\ufffd')>=0) text=new String(cueBytes,StandardCharsets.ISO_8859_1);
        text=text.replace("\ufeff","");
        Map<Source,String> needed=new LinkedHashMap<>();
        StringBuilder rewritten=new StringBuilder();
        Source first=null, active=null; String firstMode=null; int tracks=0; boolean index=false;
        long firstOffset=0; Map<Source,Long> lastIndex=new HashMap<>();
        List<Source> trackFiles=new ArrayList<>();List<Long> trackOffsets=new ArrayList<>();
        for(String line:text.split("\\r?\\n")) {
            Matcher m=FILE.matcher(line);
            if(m.matches()) {
                if(!m.group(3).equalsIgnoreCase("BINARY")) throw new IOException("仅支持原盘BINARY BIN轨道");
                String ref=safe(base+safe(m.group(1)!=null?m.group(1):m.group(2)));
                Source src=byName.get(ref.toLowerCase(Locale.ROOT));
                if(src==null) throw new IOException("缺少轨道："+ref+"。请重新选择完整CUE/BIN或整个文件夹");
                if(needed.containsKey(src))throw new IOException("同一BIN不得重复FILE声明");
                needed.put(src,String.format(Locale.ROOT,"track-%02d.bin",needed.size()+1));
                active=src;
                rewritten.append("FILE \"").append(needed.get(src)).append("\" BINARY\n");
            } else {
                Matcher t=TRACK.matcher(line);
                if(t.matches()) {
                    if(active==null) throw new IOException("TRACK之前缺少FILE");
                    if(tracks>0&&!index) throw new IOException("轨道缺少INDEX 01");
                    tracks++; index=false;
                    if((t.group(1).length()>2 || Integer.parseInt(t.group(1))!=tracks)) throw new IOException("轨道编号必须从01连续排列");
                    String mode=t.group(2).toUpperCase(Locale.ROOT);
                    if((tracks>1&&!mode.equals("AUDIO"))||!Arrays.asList("AUDIO","MODE1/2352").contains(mode)) throw new IOException("不支持轨道格式："+mode);
                    if(tracks==1) { first=active; firstMode=mode; }
                }
                String trimmed=line.trim();
                if(trimmed.toUpperCase(Locale.ROOT).startsWith("FILE ")||trimmed.toUpperCase(Locale.ROOT).startsWith("TRACK ")&&!t.matches()) throw new IOException("无效CUE声明："+trimmed);
                Matcher ix=Pattern.compile("(?i)^INDEX\\s+(00|01)\\s+(\\d+):(\\d+):(\\d+)$").matcher(trimmed);
                if(ix.matches()) {
                    if(tracks==0||active==null)throw new IOException("INDEX之前缺少TRACK");
                    if(ix.group(2).length()>3||ix.group(3).length()>2||ix.group(4).length()>2)throw new IOException("INDEX时间过长");
                    long min=Long.parseLong(ix.group(2)); int sec=Integer.parseInt(ix.group(3)),frame=Integer.parseInt(ix.group(4));
                    if(min>999||sec>=60||frame>=75)throw new IOException("无效INDEX时间");
                    long offset=((min*60+sec)*75+frame)*(tracks==1&&"MODE1/2048".equals(firstMode)?2048:2352);
                    if(offset<lastIndex.getOrDefault(active,0L)||active.size()>=0&&offset>=active.size())throw new IOException("INDEX超出轨道或倒序");
                    lastIndex.put(active,offset);
                    if(ix.group(1).equals("01")) { if(index)throw new IOException("重复INDEX 01"); index=true;trackFiles.add(active);trackOffsets.add(offset/2352); if(tracks==1)firstOffset=offset; }
                } else if(trimmed.toUpperCase(Locale.ROOT).startsWith("INDEX "))throw new IOException("无效INDEX声明");
                if(t.matches()) rewritten.append(String.format(Locale.ROOT,"  TRACK %02d %s\n",tracks,t.group(2).toUpperCase(Locale.ROOT)));
                else if(ix.matches()) rewritten.append("    INDEX ").append(ix.group(1)).append(" ").append(ix.group(2)).append(":").append(ix.group(3)).append(":").append(ix.group(4)).append('\n');
                else if(trimmed.toUpperCase(Locale.ROOT).startsWith("PREGAP")||trimmed.toUpperCase(Locale.ROOT).startsWith("POSTGAP")) {
                    if(!trimmed.matches("(?i)(PRE|POST)GAP\\s+00:00:00"))throw new IOException("暂不支持CUE虚拟PREGAP/POSTGAP，请使用包含完整间隙数据的原盘BIN/CUE");
                } else if(!trimmed.isEmpty()&&!trimmed.toUpperCase(Locale.ROOT).startsWith("REM ")&&!trimmed.toUpperCase(Locale.ROOT).startsWith("TITLE ")&&!trimmed.toUpperCase(Locale.ROOT).startsWith("PERFORMER ")&&!trimmed.toUpperCase(Locale.ROOT).startsWith("FLAGS ")) throw new IOException("不支持CUE声明："+trimmed);
            }
        }
        if(tracks!=13||!index||first==null||"AUDIO".equals(firstMode)) throw new IOException("原盘必须包含13轨（1数据轨和12音轨），且每轨有INDEX 01");
        long total=0; for(Source s:needed.keySet()) if(s.size()>0) total+=s.size();
        if(total>home.getUsableSpace()-16L*1024*1024) throw new IOException("空间不足：需要额外约"+(total/1024/1024)+" MiB；旧资源会保留到成功后");
        File staging=new File(home,"pending-"+UUID.randomUUID());
        if(!staging.mkdir()) throw new IOException("无法创建导入临时目录");
        File committed=null;
        try {
            long done=0;
            for(Map.Entry<Source,String> item:needed.entrySet()) {
                Source src=item.getKey(); long copied=0;
                try(InputStream in=src.open(); FileOutputStream out=new FileOutputStream(new File(staging,item.getValue()))) {
                    byte[] buf=new byte[1024*1024]; int n;
                    while((n=in.read(buf))!=-1) { check(cancel); out.write(buf,0,n); copied+=n; done+=n; progress.update("导入 "+src.name()+" · "+done/1024/1024+" MiB"+(total>0?" / "+total/1024/1024+" MiB":"")); }
                    out.getFD().sync();
                }
                if(lastIndex.getOrDefault(src,0L)>=copied)throw new IOException("INDEX超出实际轨道长度："+src.name());
                if(copied==0||(src.size()>=0&&copied!=src.size())) throw new IOException("轨道复制不完整："+src.name());
                if(copied%(src==first&&"MODE1/2048".equals(firstMode)?2048:2352)!=0) throw new IOException("轨道不是完整扇区："+src.name());
            }
            check(cancel);
            long baseSector=0;Map<Source,Long> fileStarts=new HashMap<>();
            for(Map.Entry<Source,String> item:needed.entrySet()){fileStarts.put(item.getKey(),baseSector);baseSector+=new File(staging,item.getValue()).length()/2352;}
            if(baseSector!=expectedSectors||trackOffsets.size()!=expectedToc.length)throw new IOException("不是此版支持的完整13轨布局/音轨可能截断");
            for(int i=0;i<expectedToc.length;i++)if(fileStarts.get(trackFiles.get(i))+trackOffsets.get(i)!=expectedToc[i])throw new IOException("不是此版支持的完整13轨布局：第"+(i+1)+"轨起点不符");
            try(RandomAccessFile data=new RandomAccessFile(new File(staging,needed.get(first)),"r")) {
                data.seek(firstOffset+("MODE1/2048".equals(firstMode)?0:16));
                byte[] header=new byte[256]; data.readFully(header);
                String h=new String(header,StandardCharsets.US_ASCII);
                if(!h.startsWith("SEGA SEGASATURN")||!h.substring(0x20,0x30).contains("T-37401H")||!h.substring(0x2a,0x30).trim().equals("V1.000")) throw new IOException("不是支持的仙剑土星原盘 T-37401H V1.000");
            }
            Files.write(new File(staging,"disc.cue").toPath(),rewritten.toString().getBytes(StandardCharsets.UTF_8));
            String id="disc-"+UUID.randomUUID(); committed=new File(home,id);
            Files.move(staging.toPath(),committed.toPath(),StandardCopyOption.ATOMIC_MOVE);
            check(cancel);
            File pointer=new File(home,"current.new");
            try(FileOutputStream out=new FileOutputStream(pointer)) { out.write(id.getBytes(StandardCharsets.UTF_8)); out.getFD().sync(); }
            Files.move(pointer.toPath(),new File(home,"current").toPath(),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
            // Retain older generations while another Activity may be starting SDL.
            // They can be safely reclaimed on a later cold launcher start under the same lock.
            return new File(committed,"disc.cue");
        } catch(IOException e) {
            if(committed!=null) { File c=current(home); if(c==null||!c.getParentFile().equals(committed)) remove(committed); }
            throw e;
        } finally { remove(staging); }
    }
    static void remove(File f) { if(f.isDirectory()) { File[] a=f.listFiles(); if(a!=null) for(File x:a) remove(x); } f.delete(); }
}
