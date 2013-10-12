    	$(function(){
    		
    		var handle = function(data){	
				try{
					
        		}
        		catch (err){
        			
        		}
			};
			
			var ws = new WebSocket('ws://localhost:9999/update');
			var start = function(){
				ws.onopen = function()
			    {
			
				};
			    ws.onmessage = function (event) 
			    { 
			     try{
			     		var buffer = $.parseJSON(event.data);		     		
			     		if(buffer && buffer !== '' && isNaN(parseInt(buffer,16))){
			     			handle($.parseJSON(buffer));
			     		}
			     		
			       }catch(err)
			       {
					  uptime.html("socket error:"+err.message);
			       }
			    };
			    ws.onclose = function()
			    { 			    	
			    	uptime.html('offline');
			    };
		   }//end start
		    
		   //lets begin processing live stream
		   start();
		})