# How gdsWriter works 

Our files are  very big so we need to write them out as we go or else we will run out of memory. To do this we use `gdsWriter.write()` but it is poorly documented.

THe test program shows that we need to manually write out any dependancies first before writing an SREF. I guess this is better behaivior since it measn the gdsWriter does not
need to have any memory, but I wish that had been documented!

Note that both ChatGPT5 and Gemini 2.5 Pro get this completely wrong and think there is a gdsWriter.write_cell() functiuon which does not exist. 
