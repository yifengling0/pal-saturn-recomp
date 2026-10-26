package org.palsaturn.android;
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.atomic.AtomicBoolean;
/** Private local integration test. No source disc bytes are committed or embedded. */
public class RealDiscImportTest {
 public static void main(String[] a)throws Exception {
  File dir=new File(a[0]);List<DiscImport.Source>s=new ArrayList<>();
  for(String name:new String[]{"pal_t37401h_13tr.cue","pal_t37401h_v1000_jt.bin"}) {File f=new File(dir,name);s.add(new DiscImport.Source(){public String name(){return f.getName();}public long size(){return f.length();}public InputStream open()throws IOException{return new FileInputStream(f);}});}
  File home=Files.createTempDirectory("pal-real-import-").toFile();
  try {File cue=DiscImport.run(home,s,new AtomicBoolean(),x->{});if(!cue.isFile())throw new AssertionError();System.out.println("PASS real-disc CUE/BIN copy, 13 tracks, private seekable rewrite");}finally{DiscImport.remove(home);}
 }
}
