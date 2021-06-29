import React from 'react';
import { Typography } from '@material-ui/core';

class Auth extends React.Component {

    constructor(props) {
        super(props);

        this.state = {};
    };

    // begin authentication
    componentDidMount() {
        
        // access token is passed in the anchor field for some reason
        let queryString = window.location.hash.replace(/^#/, '?')
        let urlParams = new URLSearchParams(queryString)

        // if token is present - resolve username
        if (urlParams.has('access_token')) {
            
            let xhr_request = new XMLHttpRequest()
            xhr_request.open("GET", window.ENV.BACKEND_ROUTE + "/username" + "?" + new URLSearchParams({ token: urlParams.get('access_token') }).toString())

            // API response callback
            xhr_request.onreadystatechange = function() {

                if (xhr_request.readyState == XMLHttpRequest.DONE) {

                    // finish authentication if username is valid
                    if (xhr_request.status == 200) {

                        this.props.finishAuthentication(urlParams.get('access_token'), xhr_request.responseText)

                    // redirect to OAuth if username is invalid
                    } else {
                    
                        this.redirect()
    
                    }

                }

            }.bind(this)

            xhr_request.send()
        }

        // redirect to authentication screen if access token is not present/valid
        else {
            this.redirect()
        }
    }

    redirect() {
        let redirectUrl = window.ENV.OAUTH_ENDPOINT + '/oauth/authorize?'

        // parameters passed to OpenShift OAuth server
        let redirectParams = new URLSearchParams({
            client_id: window.ENV.OAUTH_CLIENT_ID,
            redirect_uri: window.location.origin,
            response_type: 'token'
        })

        // redirect to OAuth server
        window.location.replace(redirectUrl + redirectParams.toString())
    }

    render() {

        return (
            <div>
                <Typography variant="subtitle2" color='textSecondary'>
                    Authenticating...
                </Typography>
            </div>
        )
    }

}

export default Auth;