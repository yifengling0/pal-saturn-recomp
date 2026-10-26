package org.palsaturn.android;
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;
public class DiscImportTest {
 static DiscImport.Source source(String name,byte[] bytes){return new DiscImport.Source(){public String name(){return name;}public long size(){return bytes.length;}public InputStream open(){return new ByteArrayInputStream(bytes);}};}
 static byte[] data(){byte[] d=new byte[2352*32];System.arraycopy("SEGA SEGASATURN  ".getBytes(),0,d,16,16);System.arraycopy("T-37401H  V1.000".getBytes(),0,d,16+0x20,16);return d;}
 static DiscImport.Source cue(String ref){StringBuilder c=new StringBuilder("FILE \""+ref+"\" BINARY\nTRACK 01 MODE1/2352\nINDEX 01 00:00:00\n");for(int n=2;n<=13;n++)c.append(String.format("TRACK %02d AUDIO\nINDEX 01 00:00:%02d\n",n,n+16));return source("disc.cue",c.toString().getBytes(StandardCharsets.UTF_8));}

 static File run(File home,List<DiscImport.Source> sources,AtomicBoolean cancel,DiscImport.Progress progress)throws IOException{return DiscImport.runWithLayout(home,sources,cancel,progress,new long[]{0,18,19,20,21,22,23,24,25,26,27,28,29},32);}
 static int passed=0;
 static void reject(File home,List<DiscImport.Source> s,AtomicBoolean cancel)throws Exception{File before=DiscImport.current(home);try{run(home,s,cancel,x->{});throw new AssertionError("accepted invalid import");}catch(IOException expected){}if(!Objects.equals(before,DiscImport.current(home)))throw new AssertionError("old resources changed");passed++;}
 public static void main(String[] args)throws Exception{
  File home=Files.createTempDirectory("pal-import-").toFile();AtomicBoolean no=new AtomicBoolean();
  byte[] valid=data();DiscImport.Source bin=source("GAME.BIN",valid);
  File first=run(home,Arrays.asList(cue("game.bin"),bin),no,x->{});if(!first.isFile())throw new AssertionError();passed++;
  reject(home,Arrays.asList(cue("missing.bin"),bin),no);
  reject(home,Arrays.asList(cue("../outside.bin"),bin),no);
  reject(home,Arrays.asList(cue("/absolute.bin"),bin),no);
  reject(home,Arrays.asList(cue("GAME.BIN"),bin,source("game.bin",valid)),no);
  reject(home,Arrays.asList(cue("GAME.BIN"),bin,source("second.cue",new byte[0])),no);
  reject(home,Arrays.asList(cue("GAME.BIN"),source("GAME.BIN",new byte[2352*32])),no);
  reject(home,Arrays.asList(cue("GAME.BIN"),source("GAME.BIN",new byte[11])),no);
  reject(home,Arrays.asList(cue("GAME.BIN"),bin),new AtomicBoolean(true));
  reject(home,Arrays.asList(bin),no);
  File second=run(home,Arrays.asList(cue("GAME.BIN"),bin),no,x->{});if(!first.exists()||!second.equals(DiscImport.current(home)))throw new AssertionError();passed++;
  DiscImport.cleanup(home);if(first.exists()||!second.exists())throw new AssertionError("cleanup failed");passed++;
  DiscImport.Source badCue=source("disc.cue",new String(DiscImport.readSmall(cue("GAME.BIN")),StandardCharsets.UTF_8).replace("TRACK 01","TRACK 999999999999999999999999").getBytes(StandardCharsets.UTF_8));
  reject(home,Arrays.asList(badCue,bin),no);
  String text=new String(DiscImport.readSmall(cue("GAME.BIN")),StandardCharsets.UTF_8);
  reject(home,Arrays.asList(source("disc.cue",text.replace("00:00:00","9999999999999999999:00:00").getBytes()),bin),no);
  reject(home,Arrays.asList(source("disc.cue",(text+"PREGAP 00:02:00\n").getBytes()),bin),no);
  reject(home,Arrays.asList(source("disc.cue",text.replace("MODE1/2352","MODE1/2048").getBytes()),bin),no);
  DiscImport.Source unknown=new DiscImport.Source(){public String name(){return "GAME.BIN";}public long size(){return -1;}public InputStream open(){return new ByteArrayInputStream(new byte[2352]);}};
  reject(home,Arrays.asList(cue("GAME.BIN"),unknown),no);
  try(RandomAccessFile guard=new RandomAccessFile(new File(home,"resource.lock"),"rw");java.nio.channels.FileLock lock=guard.getChannel().lock()){reject(home,Arrays.asList(cue("GAME.BIN"),bin),no);DiscImport.cleanup(home);if(!second.exists())throw new AssertionError("cleanup during game");}
  File lower=run(home,Arrays.asList(source("disc.cue",text.toLowerCase(Locale.ROOT).getBytes()),bin),no,x->{});if(!Files.readString(lower.toPath()).contains("TRACK 01 MODE1/2352"))throw new AssertionError("noncanonical CUE");passed++;
  reject(home,Arrays.asList(cue("GAME.BIN"),source("GAME.BIN",Arrays.copyOf(valid,2352*31))),no);
  reject(home,Arrays.asList(source("disc.cue",text.replace("00:00:29","00:00:30").getBytes()),bin),no);
  DiscImport.remove(home);System.out.println("PASS "+passed+" import cases");
 }
}
